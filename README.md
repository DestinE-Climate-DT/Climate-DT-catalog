# Climate-DT-catalog

This is the AQUA catalog for Climate DT. Includes catalogs for levante, lumi, MN5 and leonardo.
This repository focuses on the catalog, the main AQUA codebase is open-sourced and can be found [here](https://github.com/DestinE-Climate-DT/AQUA)
## Available catalogs

1. ci: Catalog for the CI/CD tests of AQUA.
2. climatedt-e25.1: Catalog for the Climate DT E suite 25.1 experiments.
3. climatedt-o25.1: Catalog for the Climate DT O suite 25.1 experiments.
4. climatedt-phase1: Catalog for the Climate DT phase1 production experiments. (Lumi, LRA on Levante and MN5 as well)
5. leonardo: Catalog for the Leonardo HPC.
6. levante: Catalog for the Levante HPC.
7. lumi-phase1: Catalog for the LUMI HPC development phase1
8. lumi-phase2: Catalog for the LUMI HPC development phase2
9. mn5-eerie: Catalog for the EERIE project in the MN5 machine
10. mn5-phase2: Catalog for the MN5 HPC development phase2
11. nextgems3: Catalog with the nextGEMS cycle3 experiments. (Levante)
12. nextgems4: Catalog with the nextGEMS cycle4 experiments. (Levante)
13. nord4-eerie: Catalog for the EERIE project in the Nord4 machine
14. obs: Catalog with the observational datasets. (multi machine)
15. template: A template catalog to be used for new catalog generation

If a catalog has some errata or some work to be done, a README file is present in the catalog folder.

## Check the catalogs

To check that your changes to the catalog are correct, you can use the aqua code and run the following command:

```bash
aqua add catalog_name -e /path/to/repo/catalogs/catalog_name
```

If you want to know more on the AQUA code, please refer to the [AQUA documentation](https://aqua.readthedocs.io/en/latest/index.html).
This test can also be run in the CI/CD pipeline, please set the label as `ready to merge` to enable the test.
It is a requirement to successfully pass the test before merging the PR.

## License

Climate-DT-catalog is distributed as open source software under Apache 2.0 License. The copyright owner is the European Union, represented by the European Commission. The development of Climate-DT-catalog has been funded by the European Union through Contract `DE_340_CSC - Destination Earth Programme Climate Adaptation Digital Twin (Climate DT)`. Further info can be found at https://destine.ecmwf.int/ and https://destination-earth.eu/