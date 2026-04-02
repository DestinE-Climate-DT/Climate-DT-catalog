import argparse
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
    logger = log_configure(log_name="Reader tests", log_level="WARNING")

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

    for model_name, exp_name, source_name in tuples:
        label = f"{catalog}/{model_name}/{exp_name}/{source_name}"
        logger.info(f"Testing: {label}.")

        if source_name not in ("lra-r100-monthly", "lra-r100-monthly-zarr"):
            try:
                reader = Reader(catalog=catalog, model=model_name, exp=exp_name, source=source_name,
                                engine="polytope", loglevel='CRITICAL')
                logger.debug(f"Successfully created Reader for {label}.")
                data = reader.retrieve()
                logger.debug(f"Successfully retrieved data for {label}.")
            except Exception as e:
                logger.error(f"Failed to create Reader or retrieve data for {label}: {e}")
        else:
            logger.debug(f"Skipping {label}, not available online.")
