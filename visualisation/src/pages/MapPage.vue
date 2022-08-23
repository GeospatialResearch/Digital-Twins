<template>
  <!-- The page that shows the map for the Digital Twin -->
  <MapViewer
    :init-lat="kaiapoi.latitude"
    :init-long="kaiapoi.longitude"
    :cesium-access-token="cesiumApiToken"
  />
</template>

<script lang="ts">
import Vue from 'vue';
import {MapViewer} from 'geo-visualisation-components/src/components';

export default Vue.extend({
  name: 'MapPage',
  components: {
    MapViewer,
  },
  data() {
    return {
      kaiapoi: {
        latitude: -43.380881,
        longitude: 172.655714
      },
      cesiumApiToken: process.env.VUE_APP_CESIUM_ACCESS_TOKEN,
    }
  },
});
</script>

<style>
</style>
