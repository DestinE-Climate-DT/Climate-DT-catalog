import argparse
from collections import defaultdict
from typing import Iterable
from aqua.core import Reader, show_catalog_content
from aqua.core.logger import log_configure


def _iter_sources(exp_node: object) -> Iterable[str]:
    """Extract source names from a model/exp node returned by show_catalog_content."""
    if isinstance(exp_node, dict):
        for source_name in exp_node:
            if isinstance(source_name, str) and not source_name.startswith("_"):
                yield source_name
        return

    if isinstance(exp_node, (list, tuple, set)):
        for source_name in exp_node:
            if isinstance(source_name, str):
                yield source_name


def iter_model_exp_source(
    content: object, catalog_name: str | None = None
) -> Iterable[tuple[str, str, str]]:
    """Yield all model/exp/source combinations from catalog content."""
    if not isinstance(content, dict):
        return

    # Some AQUA versions return {catalog_name: {...models...}}.
    if catalog_name and catalog_name in content and isinstance(content[catalog_name], dict):
        content = content[catalog_name]

    for model_name, model_node in content.items():
        if not isinstance(model_name, str) or model_name.startswith("_"):
            continue
        if not isinstance(model_node, dict):
            continue

        for exp_name, exp_node in model_node.items():
            if not isinstance(exp_name, str) or exp_name.startswith("_"):
                continue

            for source_name in _iter_sources(exp_node):
                yield model_name, exp_name, source_name


if __name__ == "__main__":
    logger = log_configure(log_name="Reader tests", log_level="INFO")

    logger.info("Testing Reader access to catalog content...")

    # Create the parser
    parser = argparse.ArgumentParser(
        description="Validate Reader for a specific catalog."
    )
    parser.add_argument(
        "--catalog",
        type=str,
        default="climatedt-gen2",
        help="Name of the catalog to test (default: climatedt-gen2)",
    )
    args = parser.parse_args()

    catalog = args.catalog
    logger.info(f"Testing catalog: {catalog}")

    content = show_catalog_content(catalog=catalog)
    tuples = list(iter_model_exp_source(content, catalog_name=catalog))
    failures: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    skipped_labels: list[str] = []
    tested_sources = 0
    successful_sources = 0

    for model_name, exp_name, source_name in tuples:
        label = f"{catalog}/{model_name}/{exp_name}/{source_name}"
        logger.debug(f"Testing: {label}.")

        if source_name not in ("lra-r100-monthly", "lra-r100-monthly-zarr"):
            tested_sources += 1
            try:
                # Setting up for polytope sources and without test of grids and areas.
                reader = Reader(catalog=catalog, model=model_name, exp=exp_name, source=source_name,
                                engine="polytope", loglevel='CRITICAL', areas=False)
                logger.debug(f"Successfully created Reader for {label}.")
                data = reader.retrieve()
                logger.debug(f"Successfully retrieved data for {label}.")
                successful_sources += 1
            except Exception as e:
                logger.error(f"Failed to retrieve data for {label}: {e}")
                failures[(catalog, model_name, exp_name)].append((source_name, str(e)))
        else:
            skipped_labels.append(label)
            logger.debug(f"Skipping {label}, not available online.")

    failed_source_count = sum(len(source_failures) for source_failures in failures.values())

    logger.info("Run summary")
    logger.info(f"Validated sources: {tested_sources}")
    logger.info(f"Successful sources: {successful_sources}")
    logger.info(f"Skipped sources: {len(skipped_labels)}")
    logger.info(f"Failed sources: {failed_source_count}")

    if skipped_labels:
        logger.info("Skipped entries:")
        for skipped_label in skipped_labels:
            logger.info(f"  - {skipped_label}")

    if failures:
        logger.info("Failed experiments:")
        for (_, model_name, exp_name), source_failures in sorted(failures.items()):
            logger.info(f"  - {catalog}/{model_name}/{exp_name}")
            for source_name, error_message in source_failures:
                logger.info(f"      source={source_name}: {error_message}")
    else:
        logger.info("All tested experiments completed successfully.")
