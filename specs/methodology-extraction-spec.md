# fish scales

## Background
The analysis of tubercle diameter and density on the ganoine surface of Lepisosteidae scales is a technique that is used to differentiate species when limited information is available, both extant and extinct species.

There are articles (originals in French), translated into English about this in the "papers" subfolder.

## English translation of papers
- In a first step we had the documents translated into english as the use does not speak French that well.
- These documents are in the subfolder "papers/english_translations"

## Pseudo-code design
These papers (with the French obviously taking priority) should be analyzed to extract the manual method used there to measure these two metrics from images.

The metrics we are are known there as:
  - TUBERCLE DIAMETER (µm)    
  - INTERTUBERCULAR SPACE
  
or their French equivlent.

These can be plotted and then clustered with othr data in a two-dimensional plot to help guide species determination.

As a first step to a python program to perform this analysis, we would like - in English - a high level pseudo-code sketch of how this could be done on images. Example images in "tiff" format are in the directory "images".

This document is now in "doc/fish-scale-metrics-extraction.md"



# Initial methodoogy calibration image
- In order to verify that this works I would like to use all possible images and information from the
  papers to generate test images and results that we can use to. 
  
- Please generate a list of images, pulled from those papers, with expected results, place the test images in a new directory "test_images", and create a markdown document.

- This test images markdown document should listing 
    - the images
    - what paper they come from
    - the expected metric results that would result from applying our (to be written) program    
 
Do not write the program for now. At the moment we just want to see how it would work.
