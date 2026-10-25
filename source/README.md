# Source

MotoMedic answers from one document, and this folder holds it with its metadata.

| File | What it is |
| --- | --- |
| [royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf) | The Royal Enfield New Himalayan 450 BS6 owner's manual: 149 pages, English, edition RAM00818/A, 4 November 2025. SHA-256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. |
| [source_manifest.json](source_manifest.json) | Immutable metadata: file, hash, edition, variant (Himalayan BS6) and applicability policy. It also holds the verified OEM support route `mailto:support@royalenfield.com`, with its market-fit note (India route; market fit pending). The runtime reads this file at startup. |
| [reviewed_graph_links.json](reviewed_graph_links.json) | Object links used by the base ingestion job ([ingest/](../ingest/README.md)). Ingestion reads it from next to the source manifest. It is not used at answer time. |

The manual is an owner's manual, not a service manual, so MotoMedic cannot answer beyond it. The repository publishes the manual for inspection under the owner's public-review scope. The rider UI shows released answers and page references only, never excerpts or page images.

Changing the manual or its manifest creates a new source, which needs a new index and a new release.
