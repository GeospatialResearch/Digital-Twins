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
    <b-button variant="primary" @click="refreshModel">Click here after generating</b-button>
    <img id="legend" src="legend.png"/>
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import * as Cesium from "cesium";
import {MapViewer} from 'geo-visualisation-components/src/components';
import titleMixin from "@/mixins/title";
import {MapViewerDataSourceOptions, Scenario} from "geo-visualisation-components/dist/types/src/types";
import axios from "axios";

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
  created() {
    this.initDataSources();
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
    onTaskPosted(event: any) {
      console.log(event)
    },
    onTaskCompleted(event: any) {
      console.log(event)
    },
    async refreshModel() {
      // const wms_details = await axios.get("http://localhost:5000/model/PLACEHOLDER_MODEL_ID")
      //
      // this.scenarios = [
      //   // {
      //   //   name: "Without climate change",
      //   //   // waterElevationAssetId: 1347528,
      //   //   ionAssetIds: [floodRasterBaseline]
      //   // },
      //   {
      //     name: "With climate change",
      //     // waterElevationAssetId: 1347532,
      //     // ionAssetIds: [floodRasterClimate]
      //     imageryProviders: [
      //       new Cesium.WebMapServiceImageryProvider({
      //         url: wms_details.data.url,
      //         layers: wms_details.data.layers,
      //         parameters: {
      //           transparent: true,
      //           format: "image/png",
      //         },
      //       })
      //     ]
      //   }
      // ]
      console.log("refreshModel()");

    },
    async initDataSources() {
      const geoJsonDataSources = await this.loadGeoJson(9);
      this.dataSources = {
        geoJsonDataSources,
        // name: "scenario 1"
        // terrainAssetId: 1347527
      };

      const floodRasterBaseline = 1345828;
      const floodRasterClimate = 1345829;
      this.refreshModel()
    },
    async loadGeoJson(scenarioId: number): Promise<Cesium.GeoJsonDataSource[]> {
      // const buildingStatusUrl = `http://localhost:8088/geoserver/digitaltwin/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=digitaltwin%3Abuilding_flood_status&outputFormat=application%2Fjson&srsName=EPSG:4326&viewparams=scenario:${scenarioId}&cql_filter=bbox(geometry,172.6601121,-43.3780373,172.6607974,-43.3784382,'EPSG:4326')`
      const buildingStatusUrl = "buildings_baseline.geojson"
      console.log("loading geojson")
      const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
      buildingStatusUrl, {
        strokeWidth: 3,
        fill: Cesium.Color.DARKRED,
        stroke: Cesium.Color.RED
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
          // extrudedHeight: 4
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
