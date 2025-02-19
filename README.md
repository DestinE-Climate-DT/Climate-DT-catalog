# Climate-DT-catalog

This is the AQUA catalog for Climate DT. Includes catalogs for levante, lumi, MN5 and leonardo.
This repository focuses on the catalog, the main AQUA codebase is open-sourced and can be found [here](https://github.com/DestinE-Climate-DT/AQUA)
## Available catalogs

1. ci: Catalog for the CI/CD tests of AQUA.
2. climatedt-e25.1: Catalog for the Climate DT E suite 25.1 experiments.
3. climatedt-phase1: Catalog for the Climate DT phase1 production experiments. (Lumi, LRA on Levante and MN5 as well)
4. leonardo: Catalog for the Leonardo HPC.
5. levante: Catalog for the Levante HPC.
6. lumi-phase1: Catalog for the LUMI HPC development phase1
7. lumi-phase2: Catalog for the LUMI HPC development phase2
8. mn5-phase2: Catalog for the MN5 HPC development phase2
9. nextgems3: Catalog with the nextGEMS cycle3 experiments. (Levante)
10. nextgems4: Catalog with the nextGEMS cycle4 experiments. (Levante)
11. obs: Catalog with the observational datasets. (multi machine)

If a catalog has some errata or some work to be done, a README file is present in the catalog folder.

## Check the catalogs

To check that your changes to the catalog are correct, you can use the aqua code and run the following command:

```bash
aqua add catalog_name -e /path/to/repo/catalogs/catalog_name
```

If you want to know more on the AQUA code, please refer to the [AQUA documentation](https://aqua.readthedocs.io/en/latest/index.html).
This test can also be run in the CI/CD pipeline, please set the label as `ready to merge` to enable the test.
It is a requirement to successfully pass the test before merging the PR.