# PetCare demo pet photos

This folder contains 68 synthetic profile photos for local demos: 32 dogs, 32 cats, and 4 earlier sample photos. The 64 new portraits were generated with AI and cropped from contact sheets for the demo catalog.

All pet profiles and images are fictional. They are not live shop inventory, adoption listings, or images of identified real animals. Do not use them as evidence of real stock or for animal-identification claims.

The seed maps `demo-dog-01.png`–`demo-dog-32.png` and `demo-cat-01.png`–`demo-cat-32.png` to PET-101–PET-164. Existing sample photos map to PET-001–PET-004. Run `python -m petcare.database.seed` against a `_dev` or `_test` database to load the new records and images.
