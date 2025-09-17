# Use layers from web data sources (e.g LINZ layers):
To use web layers you have two options. 
Either you can access add the layers using the front-end interface and the data will not be stored on the backend, or you can download the data to the backend.
Both approaches are fine to use.


Notes on each approach are below.
- ## Through web interface
1. Open the terria interface (see instructions in repo `readme.md` on starting digital twin)
2. Click "Upload Data"
3. Click "Add Web Data"
4. Fill in the form with the service type and URL. I recommend WFS for vector data and WMS for raster.

- ## By Downloading to backend:
1. Open `Digital-Twins/floodresilience/static_boundary_instructions.json`.
2. Add a new layer to this file as an instruction.



# Adding static data layers to the database/terria:## Valid data types
### Vector
Vector files should be placed directly in `src/static/geo`.

Vector data CRS must be in the form `epsg:XXXX`, it does not accept arbitrary projections.

Valid file types:
- `.geojson`
- `.shp`
- `.geodb`

### 3D Extruded Vector Files
Extruded polygons are very resource intensive. 30k features are to many to display. My estimate is that fewer than 10k may be ok.

Vector files to be extruded are stored in `Digital-Twins/src/static/geo/3d`.

Each polygon should have an attribute `Ext_height` with the height in metres for the feature.

3D polygons can not be styled the standard terria way, but you can use GIS to set an attribute on each feature `fill` with an HTML colour which will set the colour.

### Raster
Raster files should be placed directly in `Digital-Twins/src/static/geo`.

Raster data must use CRS `epsg:2193`. 

Only GeoTiff files are supported. 

Each tiff must have a style file (`.sld`) with the same name beside it. You can find an example at `src/static/geo/Flood_Confidence_50yr.sld`.


# Running the scripts to upload data
1. Ensure the Digital Twin branch is set to `clevons-survey`. It will not work without this branch's code.
2. Ensure the newest images are built by running `docker compose build`.
3. Set up the Digital Twin according to the main instructions at `Digital-Twins/README.md`.
4. While inspecting the `celery_worker` logs as described in the README, wait for the following line (transient variables replaced with `x`):

    ```celery_worker_digital_twin  | [202x-0x-0x xx:xx:xx,xxx: INFO/MainProcess] Task src.tasks.add_base_data_to_db[xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx] succeeded in xx.xxxxxxxxxxxxxxs: None```