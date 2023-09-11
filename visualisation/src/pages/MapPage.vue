<template>
  <!-- The page that shows the map for the Digital Twin -->
  <div class="full-height">
    <MapViewer
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :init-height="8000"
      :cesium-access-token="cesiumApiToken"
      :data-sources="dataSources"
      :scenarios="scenarios"
      v-on:task-posted="onTaskPosted"
      v-on:task-completed="onTaskCompleted"
    />
    <img id="legend" src="legend.png"/>
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import * as Cesium from "cesium";
import {MapViewer} from 'geo-visualisation-components/src/components';
import titleMixin from "@/mixins/title";
import {MapViewerDataSourceOptions, Scenario, bbox} from "geo-visualisation-components/dist/types/src/types";

export default Vue.extend({
  name: "MapPage",
  title: "Map",
  mixins: [titleMixin],
  components: {
    MapViewer,
  },
  data() {
    return {
      kaiapoi: {
        latitude: -43.380881,
        longitude: 172.655714
      },
      dataSources: {} as MapViewerDataSourceOptions,
      scenarios: [] as Scenario[],
      cesiumApiToken: process.env.VUE_APP_CESIUM_ACCESS_TOKEN,
    }
  },
  mounted() {
    // Limit scrolling on this page
    document.body.style.overflow = "hidden"
  },
  beforeDestroy() {
    // Reset scrolling for other pages
    document.body.style.overflow = ""
  },
  methods: {
    async onTaskPosted(event: any) {
      console.log("onTaskPosted");
      this.dataSources = {}
      const bbox = event.bbox
      const geoJsonDataSources = await this.loadGeoJson(bbox)
      this.dataSources = {geoJsonDataSources}
    },
    async onTaskCompleted(event: {bbox: bbox, floodModelId: number}) {
      console.log("onTaskCompleted");
      const geoJsonDataSources = await this.loadGeoJson(event.bbox, event.floodModelId)
      const floodRasterProvider = await this.fetchFloodRaster(event.floodModelId)
      this.dataSources = {
        geoJsonDataSources,
        imageryProviders: [floodRasterProvider]
      }
    },
    async fetchFloodRaster(model_output_id: number): Promise<Cesium.WebMapServiceImageryProvider> {
      const wmsOptions = {
        url: 'http://localhost:8088/geoserver/dt-model-outputs/wms',
        layers: `output_${model_output_id}`,
        parameters: {
          service: 'WMS',
          format: 'image/png',
          transparent: true
        }
      };
      return new Cesium.WebMapServiceImageryProvider(wmsOptions);
    },
    async loadGeoJson(bbox: bbox, scenarioId = -1): Promise<Cesium.GeoJsonDataSource[]> {
      const buildingStatusUrl = 'http://localhost:8088/geoserver/digitaltwin/ows?service=WFS&version=1.0.0'
      + '&request=GetFeature&typeName=digitaltwin%3Abuilding_flood_status&outputFormat=application%2Fjson'
      + `&srsName=EPSG:4326&viewparams=scenario:${scenarioId}`
      + `&cql_filter=bbox(geometry,${bbox.lng1},${bbox.lat1},${bbox.lng2},${bbox.lat2},'EPSG:4326')`
      console.log(buildingStatusUrl)
      console.log("loading geojson")
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

      const buildingEntities = floodBuildingDS.entities.values;
      for (const entity of buildingEntities) {
        const polyGraphics = new Cesium.PolygonGraphics({
          extrudedHeight: 4
        });
        const isFlooded = entity.properties?.is_flooded?.getValue();
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
  },
  computed: {
    scenarioNames(): Array<string> {
      return this.scenarios.map(scenario => scenario.name);
    }
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
