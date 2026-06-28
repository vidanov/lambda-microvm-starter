import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import boto3
    return mo, boto3


@app.cell
def _(mo):
    mo.md("""
# Kiro + Marimo Workspace

This notebook runs in a Lambda MicroVM with:
- **Kiro CLI** for AI-assisted notebook creation
- **marimo** for interactive Python notebooks
- **S3 sync** for persistent storage

Create notebooks here, they auto-sync to S3 every 60 seconds.
""")
    return


@app.cell
def _(mo, boto3):
    # List S3 buckets to verify AWS access
    try:
        s3 = boto3.client("s3")
        buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
        mo.md(f"### ✅ AWS access works\\n\\nFound **{len(buckets)}** buckets: {', '.join(buckets[:5])}")
    except Exception as e:
        mo.md(f"### ⚠️ AWS access not configured\\n\\n`{e}`\\n\\nSet `NOTEBOOK_BUCKET` env var and attach an IAM role with S3 permissions.")
    return


if __name__ == "__main__":
    app.run()
