<template>
  <!-- The page that shows the map for the Digital Twin -->
  <div>
    <MapViewer
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :cesium-access-token="cesiumApiToken"
      :data-sources="dataSources"
      :scenarios="scenarios"
    />
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import * as Cesium from "cesium";
import {MapViewer} from 'geo-visualisation-components/src/components';
import titleMixin from "@/mixins/title";
import {MapViewerDataSourceOptions, Scenario} from "geo-visualisation-components/dist/types/src/types";

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
  methods: {
    async loadDataSources() {
      const geoJsonDataSources = await this.loadGeoJson();
      this.dataSources = {
        geoJsonDataSources,
      };

      const floodRasterScen1 = 946761;
      const floodRasterScen2 = 1335686;

      this.scenarios = [
        {name: "Without climate change", ionAssetIds: [floodRasterScen1]},
        {name: "With climate change", ionAssetIds: [floodRasterScen2]}
      ]
    },
    async loadGeoJson(): Promise<Cesium.GeoJsonDataSource[]> {
      const nonFloodBuildingDS = await Cesium.GeoJsonDataSource.load(
        "ZS_non_flood_reproj.geojson", {
          stroke: Cesium.Color.FORESTGREEN,
          fill: Cesium.Color.DARKGREEN,
          strokeWidth: 3,
        });
      const floodBuildingDS = await Cesium.GeoJsonDataSource.load(
        "ZS_flooded_reproj.geojson", {
          stroke: Cesium.Color.RED,
          fill: Cesium.Color.DARKRED,
          strokeWidth: 3,
        });
      // const allBuildings = nonFloodBuildingDS.entities.values.concat(floodBuildingDS.entities.values);
      // for (const buildingEntity of allBuildings) {
      //   const newHeight = 4 as unknown as Cesium.Property
      //   let extrudedHeight = buildingEntity?.polygon?.extrudedHeight;
      //   if (extrudedHeight != undefined) {
      //     extrudedHeight = newHeight;
      //   }
      //   console.log(`Height: ${buildingEntity.polygon?.extrudedHeight}`)
      // }
      return [nonFloodBuildingDS, floodBuildingDS];
    }
  },
  computed: {
    scenarioNames() {
      return this.scenarios.map(scenario => scenario.name);
    }
  }
});
</script>

<style>
</style>
