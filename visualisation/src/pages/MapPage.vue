<template>
  <!-- The page that shows the map for the Digital Twin -->
  <div class="full-height">
    <div v-for="column of selectionOptions" :key="column.name">
      <label>{{ column.name }}</label>
      <select v-if="column.data" v-model="selectedOption[column.name]">
        <option v-for="option of column.data" :value="option" :key="option">
          {{ option }}
        </option>
      </select>
      <input
        v-if="column.min && column.max"
        type="number"
        v-model="selectedOption[column.name]"
        :min="column.min"
        :max="column.max"
      >
    </div>
    <MapViewer
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :init-height="8000"
      :cesium-access-token="env.cesiumApiToken"
      :data-sources="dataSources"
      :scenarios="scenarios"
      :scenario-options="selectedOption"
      @task-posted="onTaskPosted"
      @task-completed="onTaskCompleted"
    />
    <img id="legend" alt="Legend graphic showing how colour relates to depth" src="viridis_legend.png">
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import * as Cesium from "cesium";
import {MapViewer} from 'geo-visualisation-components/src/components';
import titleMixin from "@/mixins/title";
import {Bbox, MapViewerDataSourceOptions, Scenario} from "geo-visualisation-components/src/types";

export default Vue.extend({
  name: "MapPage",
  title: "Map",
  mixins: [titleMixin],
  components: {
    MapViewer,
  },
  data() {
    return {
      // Start location
      kaiapoi: {
        latitude: -43.380881,
        longitude: 172.655714
      },
      // Features to display on map
      dataSources: {} as MapViewerDataSourceOptions,
      scenarios: [] as Scenario[],
      // Drop down menu options for selecting parameters
      selectionOptions: {
        year: {
          name: "Projected Year",
          min: 2023,
          max: 2300
        },
        sspScenario: {name: "SSP Scenario", data: ['SSP1-1.9', 'SSP1-2.6', 'SSP2-4.5', 'SSP3-7.0', 'SSP5-8.5']},
        confidenceLevel: {name: "Confidence Level", data: ['low', 'medium']},
        addVerticalLandMovement: {name: "Add Vertical Land Movement", data: [true, false]}
      },
      // Default selected options for parameters
      selectedOption: {
        "Projected Year": 2050,
        "SSP Scenario": 'SSP2-4.5',
        "Confidence Level": "medium",
        "Add Vertical Land Movement": true
      },
      // Environment variables
      env: {
        cesiumApiToken: process.env.VUE_APP_CESIUM_ACCESS_TOKEN,
        geoserver: {
          host: process.env.VUE_APP_GEOSERVER_HOST,
          port: process.env.VUE_APP_GEOSERVER_PORT
        },
      },
    }
  },
  async mounted() {
    // Limit scrolling on this page
    document.body.style.overflow = "hidden"
  },
  beforeDestroy() {
    // Reset scrolling for other pages
    document.body.style.overflow = ""
  },
  methods: {
    /**
     * When a task has been posted, loads building outlines for the bbox area.
     *
     * @param event The @task-posted event passed up from MapViewer
     */
    async onTaskPosted(event: {bbox: Bbox}) {
      // Wipe existing data sources while new ones are being loaded
      this.dataSources = {}
      const bbox = event.bbox
      const geoJsonDataSources = await this.loadBuildingGeojson(bbox)
      this.dataSources = {geoJsonDataSources}
    },
    /**
     * When a task has been completed, loads building outlines with flood data and flood raster for the bbox area.
     *
     * @param event The @task-completed event passed up from MapViewer
     */
    async onTaskCompleted(event: { bbox: Bbox, floodModelId: number }) {
      const geoJsonDataSources = await this.loadBuildingGeojson(event.bbox, event.floodModelId)
      const floodRasterProvider = await this.fetchFloodRaster(event.floodModelId)
      this.dataSources = {
        geoJsonDataSources,
        imageryProviders: [floodRasterProvider]
      }
    },
    /**
     * Creates ImageryProvider from geoserver WMS for the flood raster.
     *
     * @param model_output_id The id of the flood raster to fetch
     */
    async fetchFloodRaster(model_output_id: number): Promise<Cesium.WebMapServiceImageryProvider> {
      const wmsOptions = {
        url: `${this.env.geoserver.host}:${this.env.geoserver.port}/geoserver/dt-model-outputs/wms`,
        layers: `output_${model_output_id}`,
        parameters: {
          service: 'WMS',
          format: 'image/png',
          transparent: true,
          styles: 'viridis_raster'
        }
      };
      return new Cesium.WebMapServiceImageryProvider(wmsOptions);
    },
    /**
     * Loads the geojson for the building outlines for a given area.
     * If scenarioId is provided, then it colours each building depending on flood status
     * @param bbox the bounding box of the area to load
     * @param scenarioId the flood model output id
     */
    async loadBuildingGeojson(bbox: Bbox, scenarioId = -1): Promise<Cesium.GeoJsonDataSource[]> {
      // Create geoserver url based on bbox and scenarioId
      const buildingStatusUrl = `${this.env.geoserver.host}:${this.env.geoserver.port}/geoserver/digitaltwin/ows`
        + '?service=WFS&version=1.0.0&request=GetFeature&typeName=digitaltwin%3Abuilding_flood_status'
        + `&outputFormat=application%2Fjson&srsName=EPSG:4326&viewparams=scenario:${scenarioId}`
        + `&cql_filter=bbox(geometry,${bbox.lng1},${bbox.lat1},${bbox.lng2},${bbox.lat2},'EPSG:4326')`
      const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
        buildingStatusUrl, {
          strokeWidth: 3,
        });

      const floodedStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKRED,
        outlineColor: Cesium.Color.RED
      });
      const nonFloodedStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKGREEN,
        outlineColor: Cesium.Color.FORESTGREEN
      });
      const unknownStyle = new Cesium.PolygonGraphics({
        material: Cesium.Color.DARKGOLDENROD,
        outlineColor: Cesium.Color.GOLDENROD
      });

      // Add extrusion height and colour to each building
      const buildingEntities = floodBuildingDS.entities.values;
      for (const entity of buildingEntities) {
        // Base style for all polygons
        const polyGraphics = new Cesium.PolygonGraphics({
          extrudedHeight: 4
        });
        const isFlooded = entity.properties?.is_flooded?.getValue();
        // Apply different styles based on flood status
        if (isFlooded == null) {
          polyGraphics.merge(unknownStyle);
        } else if (isFlooded) {
          polyGraphics.merge(floodedStyle);
        } else {
          polyGraphics.merge(nonFloodedStyle);
        }
        if (entity.polygon != undefined) {
          polyGraphics.merge(entity.polygon);
        }
        entity.polygon = polyGraphics
      }

      return [floodBuildingDS];
    },
  }
});
</script>

<style>
#legend {
  position: absolute;
  bottom: 40px;
  right: 30px;
  height: 175px
}
</style>
