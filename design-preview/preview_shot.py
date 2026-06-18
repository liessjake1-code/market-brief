import subprocess, pathlib, sys
html = pathlib.Path("brief.preview.html")
if not html.exists():
    print("NO PREVIEW HTML — run the offline build first"); sys.exit(1)
out = pathlib.Path("/tmp/brief_preview.png")
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=2", "--window-size=720,2400",
                f"--screenshot={out}", html.resolve().as_uri()], check=True,
               capture_output=True)
print("WROTE", out, out.stat().st_size, "bytes")
