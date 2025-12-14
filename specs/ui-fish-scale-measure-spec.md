# Spec for a program to measure fish scales from tiff images, both automatically and with human editing
- This is a program that builds on `fish-scale-measure.python`,  Python CLI tool for extracting tubercle diameter and intertubercular space measurements from SEM (Scanning Electron Microscope) images of ganoid fish scales.
- It shares a project folder with it.


## Background
- Background and related information can be found in the README.md file in the root of this project, as well as in the "docs" subfolder and in the "specs" subfolder
- There is one image in particular - "test_folder/extraction_methodology.png" - that particularly well illustrates what this is about 
- we use that as a reference to test our automated extraction algorithem but the results were helpful, but not completely adaquet, thus we need to add human editing.
- We are looking to create a UI similar in appearance and handling to "scipap". An image of its UI can be found in "specs/scipap.jpg", also a Python Flask app with a multi-tabed interface.

## Purpose
This program will measure two important metrics that can be extracted from images of fish scales and subsequently be used to determine the species.

## Audience
- Primarily a palentologist doing research on fish fossilees

# Layout
- There will be an main image always present on the left side, which can be rotated and resaved.
- On the right will be a tabbed container, with the tabs corresonponding to varioius things you can do.

# Terms
- Main Image (MI) - the image being edited
- Scales and Links Overlay (SLO) - a set of circles showing the location and extent of the fish scales (FIS), and links (FIL) rerpresented as lines  showing the distance of the fish scales from their neighbors

## Use Cases
- Start-up will be a selection of files from a folder that can loaded up into the main image. It will support at lest tif, tiff, jpeg, jpg, and png.
- New Image Button on left under main image: Loads up a new image for display as the main image 
- Configure Tab sets extraction parameters. The various metrics and methods for extracing scales and links are described in docs
   - another place to find them is in the parameter list of the help for the "fish-scale-measure" program
- Extract Scales and Lliks Button on right side - discards the current SLO and uses the current extraction methods to find a new sset of FIS and FIL 
   - Only visible
   - Drawh
- Save SLO - Write the curent set of FIS adn FIL to two csv files as well as to json for furthur processing
- SLO Tab - view the numerical data of the FIL and FIS as well as their average- we use that as a reference to test our automated extraction algorithem but the results were
 and std.dev diameters and lengths respectively
- Edit Tab - Incude SLO editing buttons
    - FIS
        - Select FIS
       - Delete (Selected FIS is deleted  - there should be an are you sure button if Allow Delete below is not checked)
       - Move should allow you to click a point to which the FIS should be centered on (i.e. moved to there)
       - Change Radius - slider with butttons to increase or decrease size by a configurable percent. 
     -  FIL
      - Editing Configuration 
          - Select FIL
          - Delete Selected FIL is deleted  - there should be an are you sure button if Allow Delete below is not checked)
         - Change Radius Button percent value
         - Allow Delete without confirmation
- About tab -  should allow to view app version, python version, library vesions, build date, author email,

## File Formats
- We will save the FIS and FIL in two different formats, csv and json
   - This is because while csv is simpler and easier for downstream apps to process, json allows much richer data - including metadata to be saved
- FIS csv will have the columns,i mage filename,  "circle", circle center x and y, circle radius , and 3 more empty or zero parameters, or "elilpse" then  for an elipsethe positions of the focuses and minor and major radiuses 
 -FIS link wil have  the columns: image filename, id1, x1, y1, id2, x2, y2
 - JSON data  will have metadata, image filename, creation date and time, then a list of FIS and a list of FIL as above
 
## UI Tabs
- In ths initial version we will define three tabs on the left, Configure, SLO, About

## Sample files
- We currently have two sets of sample images in this project
   - "images" folder - 3 full sized, higher resolution, recently scanned SEM images very similar to those we actualy want to analyze
  - "test_images" folder - 13 or so smaller and older images lifted from research papers (some from the 1980s) on this topic
   

## Technology and Implementation notes
- Program should be a flask app with a javascript front/end
- The code we researched and used in the CLI program "fish-scale-measure" should be used for FIS and FIL extraction
- Use cases should be seperate execute in seperate tabs usually unless there is a large amount of overlap
- All python code should be run using the uv package manager managing a .venv dedicated for this project and shared by "fish-scales-extraction"
- An AI-powered editing and adjustment is a particularly interesting future goal
