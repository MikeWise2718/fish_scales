import httpx

  # Load an image
resp = httpx.post("http://localhost:5010/api/mcp/load-image",
      json={"path": "D:/senkenberg/fish_scales/test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif"})
print(resp.json())

  # Set calibration
resp = httpx.post("http://localhost:5010/api/mcp/calibration",
      json={"um_per_px": 0.33})
print(resp.json())

  # Get screenshot
resp = httpx.get("http://localhost:5010/api/mcp/screenshot?overlay=true")
print(f"Screenshot: {len(resp.json()['image_b64'])} chars")