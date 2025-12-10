# Spec for a program to measure fish scales from tiff images

## Purpose
THis program will measure two important metrics that can be extracted from images of fish scales and subsequently be used to determine the species.

## Audience
- Primarily a palentologist doing research on fish fossilees

## Use Cases
- Load up image for display
- Extract the metrics as desribed in docs/... 
   - Create a supporting image showing the scales and distances as in the image in specs/?.png
- Write the extracted values to a csv file for furthur processing
- Create a plot showing how the values compare to other known cases as in specs/?.png

## Technology
- Program should be a flask app with a javascript front/end
- Use cases should be seperate 
- All python code should run using the uv package manager in a .venv
