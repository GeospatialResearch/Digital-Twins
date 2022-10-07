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

      const floodRasterBaseline = 1345828;
      const floodRasterClimate = 1345829;

      this.scenarios = [
        {name: "Without climate change", ionAssetIds: [floodRasterBaseline]},
        {name: "With climate change", ionAssetIds: [floodRasterClimate]}
      ]
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
        const polyGraphics = new Cesium.PolygonGraphics();
        if (entity.properties?.flooded.getValue()) {
          floodedStyle.clone(polyGraphics);
        } else {
          nonFloodedStyle.clone(polyGraphics);
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
    scenarioNames() {
      return this.scenarios.map(scenario => scenario.name);
    }
  }
});
</script>

<style>
</style>
