# Spec for a program to measure fish scales from tiff images

## Purpose
This program will measure two important metrics that can be extracted from images of fish scales and subsequently be used to determine the species.

## Audience
- Primarily a palentologist doing research on fish fossilees

## Use Cases
- Load up image for display
- Created output data specfied in the following should go into a directory "output", in a subdirectory with a date-coded filename down to the second.
- Extract the metrics as desribed in "docs/fish-scale-metrics-extraction.md"
   - Output relevent data for each phase in text, but also create images
   - that output should also appear in a timestamped text log in the output directory
   - Create a supporting 2-part image showing the geometry scales and distances similar to the image in "specs/extraction_methodology.png"
- Write the detailed extracted metrics (one line per scale) to a csv file for furthur processing
- A readme describing what this does, how to use it, and how to run the test cases should be created

## Technology
- Language will be python
- All python code should run using the uv package manager in a .venv
- Should have command lines arguments created with rich-argparse library
- Should have colorized output created with the rich library
- The supporting image should be created with matplotlib or something better (suggest something)
- Should have a pytes suite in which the images in test_images are measured against what is expected in the test_images directory
- Code should be modular, so that it may be used in pytest, in this command line test, and later in a flask UI

