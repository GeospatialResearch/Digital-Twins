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
    this.loadDataSources();
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
    async refreshModel() {
      const wms_details = await axios.get("http://localhost:5000/model/PLACEHOLDER_MODEL_ID")

      this.scenarios = [
        // {
        //   name: "Without climate change",
        //   // waterElevationAssetId: 1347528,
        //   ionAssetIds: [floodRasterBaseline]
        // },
        {
          name: "With climate change",
          // waterElevationAssetId: 1347532,
          // ionAssetIds: [floodRasterClimate]
          imageryProviders: [
            new Cesium.WebMapServiceImageryProvider({
              url: wms_details.data.url,
              layers: wms_details.data.layers,
              parameters: {
                transparent: true,
                format: "image/png",
              },
            })
          ]
        }
      ]

    },
    async loadDataSources() {
      const geoJsonDataSources = await this.loadGeoJson();
      this.dataSources = {
        geoJsonDataSources,
        // terrainAssetId: 1347527
      };

      const floodRasterBaseline = 1345828;
      const floodRasterClimate = 1345829;
      this.refreshModel()
    },
    async loadGeoJson(): Promise<Cesium.GeoJsonDataSource[]> {
      const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
        "buildings_baseline.geojson", {
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

      const buildingEntities = floodBuildingDS.entities.values;
      for (const entity of buildingEntities) {
        const polyGraphics = new Cesium.PolygonGraphics({
          extrudedHeight: 4,
          // heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
          // zIndex: -1,
        });
        if (entity.properties?.flooded.getValue()) {
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
    }
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
