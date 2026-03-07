# Free Deployment Methodology (Recommended)

This project is best deployed free on **Streamlit Community Cloud**.

## Why this option
- Native support for Streamlit apps.
- Free public URL.
- Auto-deploy from GitHub commits.
- No server maintenance.

## Preconditions
- Your repo must contain:
  - `app.py` (entrypoint)
  - `requirements.txt` (added)
  - `.streamlit/config.toml` (added)
- Telemetry folders `February_10` ... `February_14` must be accessible by the app.

## Data strategy (important)
Streamlit Cloud has storage limits. Use one of these:

1. **Small dataset**:
- Commit `February_*` folders into the same GitHub repo.
- Set app env var `LILA_DATA_ROOT` to repo root path at runtime if needed.

2. **Large dataset (recommended)**:
- Host parquet files externally (Hugging Face Dataset / S3 / GDrive direct files).
- Add startup sync logic to download files to a local cache dir.
- Set `LILA_DATA_ROOT` to that cache dir.

## Deploy Steps (Streamlit Cloud)
1. Push this project to GitHub.
2. Open [https://share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app**.
4. Select repo/branch.
5. Set **Main file path** to `app.py`.
6. In app settings, add environment variable:
   - `LILA_DATA_ROOT` = absolute path containing `February_*` folders.
7. Deploy.

## Verify after deploy
- Open deployed URL.
- Validate:
  - Map/date/match filters populate.
  - Timeline not stuck at `00:00 / 00:00`.
  - Map + legend render correctly.
  - Map Insights and Event Summary load.

## One-command local verification
```bash
cd "/Users/hitheshkaranth/Downloads/player_data 2/lila-black-viz"
source backend/.venv/bin/activate
LILA_DATA_ROOT="/Users/hitheshkaranth/Downloads/player_data 2" streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

## Notes
- I cannot complete the final Cloud deployment click/auth steps without your GitHub/Streamlit account session.
- The codebase is now prepared for that deployment path.
