# Third-Party Notices and License Attribution

This document lists third-party software packages, vendored frontend scripts, pre-trained machine learning models, and image assets used or included with **PetCare Manager**.

> **Scope Notice**: Third-party components retain their respective upstream licenses and notices. Any first-party license later chosen for PetCare Manager applies solely to first-party source code created for this project and does not re-license third-party or vendored components (such as GSAP, ONNX models, or third-party Python packages).

---

## 1. Vendored Frontend Runtime Assets (Included in Source & Release Archive)

### GSAP (`gsap@3.15.0`)
- **Files**: `petcare/static/vendor/gsap/gsap.min.js`, `petcare/static/vendor/gsap/gsap.min.js.map`, `petcare/static/vendor/gsap/README.md`
- **Copyright**: Copyright 2026, GreenSock. All rights reserved.
- **License**: **GreenSock Standard License** (`https://gsap.com/standard-license`)
- **Upstream Tarball**: `https://registry.npmjs.org/gsap/-/gsap-3.15.0.tgz`
- **Notes**: Core/CSSPlugin runtime only. **Not MIT and not Apache-2.0.** Embedded copyright/license headers in `gsap.min.js` are preserved unchanged. Any commercial or multi-client redistribution outside GreenSock's no-charge Standard License scope requires reviewing GreenSock's licensing terms directly.

---

## 2. Pre-trained Local AI Vision ONNX Models (Included in Source & Release Archive)

Offline inference runs via `onnxruntime` CPU provider with zero outbound network calls. Integrity metadata is tracked in `petcare/vision/models/MODEL_MANIFEST.json`:

| Artifact | Role | Upstream Source | License | Size (bytes) | SHA-256 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `yolox_nano.onnx` | Stage 1 object detector (416x416) | `https://github.com/Megvii-BaseDetection/YOLOX` (`0.1.1rc0`) | **Apache-2.0** | `3,659,407` | `c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d` |
| `mobilenetv2-12.onnx` | Stage 2 crop species verifier (224x224) | `https://github.com/onnx/models` (`opset-12`) | **Apache-2.0** | `13,964,571` | `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5` |
| `mobilenetv2-12-features.onnx` | Stage 2 1280-D feature extractor | Derived from `mobilenetv2-12.onnx` (`scripts/build_mobilenetv2_feature_extractor.py`) | **Apache-2.0** | `13,964,674` | `0a15a2be5af52322c7b00bfc62b10fce4e10270c3bd60feb6f9268fcb2820f88` |

---

## 3. Python Runtime Dependencies (`requirements.txt` / `requirements.lock`)

Source archives declare dependency constraints rather than bundling Python wheels directly. Runtime environments and container images install the locked packages below:

### Copyleft Dependency with FOSS License Exception
| Package | Pinned Version (`requirements.lock`) | License | Redistribution Requirement |
| :--- | :--- | :--- | :--- |
| `mysql-connector-python` | `9.7.0` | **GNU GPLv2 (with FOSS License Exception)** | Combining or redistributing applications linked with `mysql-connector-python` in binary/container form requires either full GNU GPLv2 compliance or distribution of the combined application under an OSI-approved FOSS license covered by Oracle's FOSS License Exception. |

### Permissive Runtime Dependencies
| Package | Pinned Version (`requirements.lock`) | License |
| :--- | :--- | :--- |
| `Flask` | `3.1.3` | BSD-3-Clause |
| `Flask-WTF` | `1.3.0` | BSD-3-Clause |
| `WTForms` | `3.3.2` | BSD-3-Clause |
| `Werkzeug` | `3.1.9` | BSD-3-Clause |
| `Jinja2` | `3.1.6` | BSD-3-Clause |
| `MarkupSafe` | `3.0.4` | BSD-3-Clause |
| `itsdangerous` | `2.2.0` | BSD-3-Clause |
| `click` | `8.5.1` | BSD-3-Clause |
| `blinker` | `1.9.0` | MIT |
| `babel` | `2.18.0` | BSD-3-Clause |
| `tzdata` | `2026.6` | Apache-2.0 |
| `python-dotenv` | `1.2.4` | BSD-3-Clause |
| `pillow` | `13.0.0` | MIT-CMU |
| `qrcode` | `8.2` | BSD-3-Clause |
| `cryptography` | `50.0.2` | Apache-2.0 OR BSD-3-Clause |
| `cffi` | `2.1.1` | MIT-0 |
| `pycparser` | `3.12` | BSD-3-Clause |
| `boto3` | `1.43.126` | Apache-2.0 |
| `botocore` | `1.43.126` | Apache-2.0 |
| `s3transfer` | `0.19.3` | Apache-2.0 |
| `jmespath` | `1.1.0` | MIT |
| `urllib3` | `2.8.0` | MIT |
| `python-dateutil` | `2.9.0.post0` | Apache-2.0 OR BSD-3-Clause |
| `six` | `1.17.0` | MIT |
| `gunicorn` | `23.0.0` | MIT |
| `numpy` | `2.4.6` / `2.5.5` | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| `onnxruntime` | `1.32.0` | MIT |
| `protobuf` | `7.36.2` | BSD-3-Clause |
| `flatbuffers` | `25.12.19` | Apache-2.0 |
| `packaging` | `26.3` | Apache-2.0 OR BSD-2-Clause |
| `xlsxwriter` | `3.3.1` | BSD-2-Clause |

---

## 4. Synthetic Demo & Catalog Imagery

- **`assets/demo/pets/`** (`68` portraits + `README.md`): Synthetic AI-generated portraits (`demo-dog-01..32.png`, `demo-cat-01..32.png` plus 4 sample demo photos). Fictional demo data only; not live shop inventory or biometric animal identification claims.
- **`petcare/static/img/catalog/`** (`28` `.webp`, `10` `.svg`) and **`petcare/static/img/login/`** (`3` `.webp`): Project-created catalog product/pet thumbnails, vector fallback icons, and login illustrations.

---

## 5. Development & QA-Only Tooling (Excluded from Source Release Archive)

- **`axe-core@4.14.0`** (`tests/a11y/package.json`): **MPL-2.0** (installed solely inside gitignored `tests/a11y/node_modules/` for accessibility audits).
- **`playwright==1.64.1`**, `greenlet==3.5.6`, `pyee==14.0.0`, `typing-extensions==4.16.0` (`requirements-browser.lock`): **Apache-2.0 / MIT / PSF** (optional browser QA dependencies, excluded from `requirements.lock` and runtime container installs).
- **`bandit==1.9.4`**, **`trivy`**, **`mysql:8.4`**: External CI verification tooling only.
