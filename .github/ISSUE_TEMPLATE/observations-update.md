---
name: Observations update
about: A template to sketch the required step for the update of an observational dataset
title: "[Obs]"
labels: Observations
assignees: ''

---

**Describe the observational dataset to implement**
Describe if it is a temporal extension, a fix or a new version

**Step to be completed**

For datasets supported by `aqua-obs` (see `catalogs/obs/scripts/README.md`), `aqua-obs update <dataset>` covers download, processing and catalog adaptation.

- [ ] Download new data
- [ ] Document the retrieve of data (if data are lost in order to restore them asap)
- [ ] Do a temporary backup of old data
- [ ] Substitute data on Lumi
- [ ] Adapt the catalog
- [ ] Add to DVC
- [ ] Test the diagnostic (if possible)
- [ ] Run test
