# UI Spec Open Questions

These questions should be addressed before creating a detailed implementation plan for the fish scale measurement UI (based on `specs/ui-fish-scale-measure-spec.md`).

---

## 1. Architecture & Technology

- **Flask vs. modern alternatives**: The spec says "Flask app with JavaScript frontend." Should this be vanilla JS, or would a lightweight framework like Alpine.js, HTMX, or Vue be acceptable for better interactivity?
   - MW - I don't think that this application will every get much bigger. So unless it would make it much easier,  I say stick with Vanilla JS.


- **Image handling**: SEM images can be very large (the `images/` folder has high-res TIFFs). Should image processing happen server-side with downsampled previews sent to browser, or should we use client-side canvas manipulation?
    - MW - We can worry about that when the problem comes. I don't think we have that problem. Put that in the spec.

- **Real-time updates**: When editing FIS/FIL, should changes sync immediately to the server, or batch-save on explicit action?
    - MW - Immediately. Also statistics - that are not computationally heavy - should be updated. Put that in the spec.

---

## 2. Layout & Navigation Contradictions

- **Tab location inconsistency**: The spec says tabs are "on the right" (Use Cases section) but also "three tabs on the left" (UI Tabs section). Which is correct?
   - MW - Tabs are on the right. Please correct that in the spec.

- **Tab list mismatch**: "UI Tabs" section lists 3 tabs: Configure, SLO, About. But "Use Cases" mentions Configure, SLO, Edit, and About (4 tabs). Which is the correct set?
   - IMW -  don't care about the number, and forgot to go background and change it when I added one. We have as many tabs as we need. Please edit concrete numbers out of the spec.

- **Where does "Extract Scales and Links" button live?** The spec says "on right side" but doesn't specify which tab or if it's always visible.
    - MW - I would say it should live on the right under an "Extraction" tab and only be visible when the tab is selected.

---

## 3. Editing Workflow

- **FIS selection mechanism**: How does the user select a tubercle (FIS)?
  - Click directly on the circle? .
  - Click-and-drag marquee selection for multiple? 
  - Keyboard shortcuts (Tab to cycle)? 
  - MW - Yes, No Yes, and add this to the spec.
  

- **Visual feedback for selection**: How is a selected FIS/FIL indicated? Different color? Handles? Dashed outline? 
    - MW - Different colorspace and thicker lines I would say. Add this to the spec.

- **Adding new FIS**: The spec covers Delete, Move, Change Radius for FIS, but what about **adding** a new tubercle the algorithm missed? This seems essential for "human editing."
     - MW - I forgot it. Add it to the spec. It should be added with a mouse click on a location.

- **Adding new FIL**: Similarly, can users manually add a link between two tubercles?
     - MW - Yes,  should select - with the mouse - two tubercles. Add it to the spec.

- **Undo/Redo**: Should there be undo/redo capability for edits? This is critical for manual correction workflows.
     - MW - Yes, if it is not too hard. Add  it to the spec.

- **FIL editing incomplete**: The spec mentions "Change Radius Button percent value" for FIL, but links are lines, not circles. Is this a copy-paste error from FIS? What FIL properties can actually be edited (delete only)?
       - MW - Copy paste error. Correct it in the spec.
---

## 4. Calibration & Scale

- **Scale bar handling**: The CLI supports manual calibration (`--scale-bar-um`, `--scale-bar-px`) and auto-estimation. How does the UI handle this?
  - Should there be a "draw scale bar" tool where user clicks two points and enters the µm value?
  - Or just numeric input fields?
  
  - MW - Implement both possibilities. Add them to the spec.

- **Zoom and pan**: How does the user navigate large images? Mouse wheel zoom? Pan with drag? Zoom-to-fit button?
   - MW - Zooming and Panning and scroll bars are needed features. Add this to the spec.

- **Coordinate system**: When the image is rotated (spec mentions rotation), do FIS/FIL coordinates transform with it, or are they stored in original image coordinates?
   - MW - when rotated (90 degree and integer multiples of this are all we need) coordinates need to be transforme. add to spec.

---

## 5. Data Persistence & File Management

- **Project/session concept**: Does the app maintain a "project" or "session" concept where the user can save and reload work-in-progress?
  - MW - Not really. However the user should be able to load an image and an SLO set and continue working on it. If the SLO set has a name different from the original file name it should generate a warning, and be saved to a new file at save time. add to spec.
  - MW - If you see another need for it let me know.

- **Auto-save**: Should edits auto-save, or require explicit save action?
  - MW - require explicit save for now. add to spec

- **File naming convention**: The spec mentions saving FIS and FIL to CSV and JSON. What are the exact filenames? `<image_name>_.csv`, `<image_name>_fil.csv`, `<image_name>.json`?
  - MW - `<image_name>_tub.csv`, `<image_name>_itc.csv`, `<image_name>_slo.json` - add to spec.

- **Where are files saved?** Same directory as image? User-selected output folder? A dedicated workspace?
  - MW - a dedicated directory named slo - add to spec

- **Overwrite warning**: If output files already exist, should the app warn before overwriting?
  - MW - yes. add to spec

---

## 6. Detection Parameters (Configure Tab)

- **Which parameters to expose?** The CLI has many parameters:
  - `--threshold`, `--min-diameter`, `--max-diameter`, `--circularity`
  - `--method` (log, dog, ellipse, lattice)
  - `--clahe-clip`, `--clahe-kernel`, `--blur-sigma`
  - `--neighbor-graph` (delaunay, gabriel, rng)
  - `--profile` presets

  Should all of these be in the UI, or a simplified subset? What about profile presets?
  - MW - all of these should be in the UI including profile presets.

- **Live preview**: When parameters change, should the detection re-run automatically (expensive), or require explicit "Extract" button click?
   - MW - require explicit extract. Changed parametrs should be highlighted thogh, and navigating away from changed paraemters should evoke a warning. add to spec.

---

## 7. SLO Tab (Data View)

- **Table interactivity**: Is the numerical data table read-only, or can users edit values directly (e.g., type a new diameter)?
   - MW - Read-only - add to spec.

- **Selection sync**: If user selects a row in the table, should the corresponding FIS/FIL highlight in the image? And vice versa?
   - MW - Good idea. Add to spec.

- **Statistics display**: The spec mentions "average and std.dev diameters and lengths." Should this include the genus classification and confidence shown in CLI output?
   - MW - Not for now. Add to spec.

- **Export from this tab**: Should there be export buttons directly on this tab, or only the "Save SLO" button elsewhere?
   - MW - "Save SLO" should be a button on the right always visible. (Would be okay on the left too though) Add to spec.

---

## 8. Image Rotation

- **Rotation granularity**: "Rotate and resave" - is this 90-degree increments only, or arbitrary angles?
   - MW - 90 degree increment only. Add to spec.

- **Resave behavior**: Does "resave" mean overwrite the original file, or save as new file? Overwriting originals is destructive.
   - MW - overwrite in this case only. As it is reverseable, it is not really desctructive. Add to spec.

- **Rotation and existing SLO**: If an image is rotated after detection, what happens to the existing FIS/FIL overlay?
   - MW - it gets rotated too. Add to spec.

---

## 9. Multi-Image Workflow

- **Image list/browser**: The spec mentions loading images from a folder. Is there a file browser panel, or just a dialog?
  - MW - at application start,  and when a new image is desired,  scipap displays a new screen (see specs/scipap_image_loading.png). This is also how this app should work. Add to spec

- **Batch processing**: Should the UI support batch extraction across multiple images (like CLI `batch` command)?
  - MW - not for now. Add to spec.

- **Compare images**: Any need to view two images side-by-side for comparison?
  - MW - not for now. Add to spec.

---

## 10. Error Handling & Edge Cases

- **No tubercles detected**: What happens if extraction finds zero FIS? Error message? Allow manual addition?
   - MW - yeah, I forgot to add manual addition. Extraction finding zero is a valid but unwanted result. Add it to the spec.

- **Image loading failures**: How are corrupt or unsupported files handled?
   - MW - A clear error message should be communicated to the user,  and any logging we decide to have. Add it to the spec.

- **Large images**: Performance thresholds? Warning for images over X megapixels?
   - MW - We don't need to worry about that. Add it to the spec.

---

## 11. About Tab

- **Library versions**: Which libraries? All Python packages? Just core ones (scikit-image, scipy, flask)?
   - MW - core ones for now.
   - MW - Add it to spec.

- **Build date**: How is this determined? Git commit? Release tag? Manual version file?
   - MW - let's go with the git commit date. maybe add the commit hash while we are at it. Add it to spec.

---

## 12. Terminology Clarification

- **FIS vs tubercle**: The spec uses "FIS" (Fish Scales) but the domain and CLI use "tubercle." Should the UI use scientific terminology (tubercle) or simplified terms (scales)?
   - MW - VERY good point. I stand corrected.
   - MW - Change to all the FIS abreviations to TUB in the spec. Refer to them with their (capitalized) full name (Tubercles) when there is room in the app.

- **FIL naming**: "Fish Links" for the neighbor edges - is this the preferred term, or should it be "intertubercular connections" or similar?
   - MW - Change to all the FIL abreviations to ITC in the spec. Refer to them with their (capitalized) full name (Intertubercular Connections) when there is room in the app.

---

## Priority Questions to Resolve First

These have the highest impact on implementation planning:

1. **Tab layout and contents** - Resolve the contradictions before any UI work begins
2. **Adding new FIS/FIL** - Critical missing feature for the editing workflow
3. **Image handling strategy** - Architectural decision affects everything
4. **Parameter exposure** - What goes in Configure tab
5. **Undo/Redo** - Significant implementation effort if needed

## Aditional requirements - add these to the spec
- MW - Log Tab 
   - We need logging so there should be a Log tab. 
   - When the log tab is active the log will be displayed in a grid. 
   - Logs will be formatted as jsonl for easy viewing with Lnav.
   - Logs will be saved in a log directory with timestamps in the name accurate to the second of creation.
   - A new log file will be created for each app invokation.
   - The following events will be logged:
       - Application start and exit
       - Loading and saving images and SLOs should be logged along with statistics (like how many TUB and ITC there are). 
       - Extraction should be logs as well. 
       - Adding TUB or ITC should also be logged

- MW - Help Screen for parameters.
   - Each Extraction parameter input widget should have a help symbol that can be clicked. 
   - When it is clicked a static html formated help page should come up
   - The help page should have sections for each parameter. The link should always bring you to the section corresponding to the parameter you clicked on.
   - The help page should be located with the source code and be editable. 
   - Links to relevent wikipedia pages would be nice.