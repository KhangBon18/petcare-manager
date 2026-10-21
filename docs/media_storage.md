# Private media storage

The app stores normalized, metadata-free JPEGs outside MySQL. `MEDIA_STORAGE_BACKEND=local` is the default for development and the single-host Compose setup. Set `MEDIA_STORAGE_BACKEND=s3` to use AWS S3 or an S3-compatible provider. Image reads still pass through the authenticated app route, which checks the user's active store membership and that the filename is referenced by that store before reading the private object.

## Configuration

Set these runtime environment variables for the web service:

```dotenv
MEDIA_STORAGE_BACKEND=s3
MEDIA_S3_BUCKET=petcare-private
MEDIA_S3_REGION=ap-southeast-1
MEDIA_S3_ENDPOINT_URL=
MEDIA_S3_PREFIX=petcare
MEDIA_S3_ADDRESSING_STYLE=auto
MEDIA_S3_SERVER_SIDE_ENCRYPTION=AES256
```

Prefer the platform's workload identity/IAM role. If the provider has no workload identity, configure `MEDIA_S3_ACCESS_KEY_ID` and `MEDIA_S3_SECRET_ACCESS_KEY` as a pair in its secret manager. Never use root or account-owner keys. A custom endpoint may be used for S3-compatible providers; production requires HTTPS. `path` addressing is useful for local MinIO-style endpoints; AWS normally uses `auto`. The bucket and endpoint are not exposed to browsers and the app does not set public ACLs. Uploads request private no-store cache headers and server-side AES-256 encryption by default; a provider must also enforce bucket-level encryption and block public access.

The web identity needs only object-level `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on `arn:aws:s3:::<bucket>/<prefix>/*`. The app does not list or make buckets. Do not grant `s3:*`, ACL changes, bucket policy edits, or public-read access to the web identity. For a KMS-encrypted bucket, configure the provider to permit the workload role to use its key and set `MEDIA_S3_SERVER_SIDE_ENCRYPTION=` only when the provider's bucket policy supplies encryption; explicit SSE-KMS key selection is not currently implemented.

## Moving existing photos

Changing the backend alone does not move existing files. Keep the app on its current backend, set the S3 destination settings, then inspect the dry-run count:

```sh
python -m petcare.vision.migrate_media --from local --to s3
python -m petcare.vision.migrate_media --from local --to s3 --apply
```

The copy reads photo names referenced by both tables across all stores, uploads each object, and verifies the SHA-256 of the source and destination. It never removes source photos, can be rerun, and performs no database writes. For cutover, pause photo writes, run the copy, set `MEDIA_STORAGE_BACKEND=s3`, restart the app, and verify photos plus tenant export. Keep the local files until rollback is no longer needed. To copy back, use `--from s3 --to local` while writes are paused. The command prints counts, not filenames or customer data.

## Backup and provider checks

The local encrypted backup utility intentionally refuses S3 mode because it cannot include remote objects. Protect the database and bucket independently with the provider's backup, versioning, retention and alerting; rehearse restoring both together. Tenant export does include the selected store's referenced photo objects. There is no lifecycle/garbage-collection worker yet, so monitor for unreferenced objects and define an object-retention policy before public launch. Confirm the selected provider, IAM policy, encryption, restore path, latency and data region in a staging account; local unit tests use Boto3's stubbed S3 protocol, not real provider credentials.
