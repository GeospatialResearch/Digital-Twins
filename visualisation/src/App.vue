<template>
  <!-- The Vue app main context -->
  <div id="app">
    <MapViewer
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :cesium-access-token="cesiumApiToken"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue';
import MapViewer from 'geo-visualisation-components'

export default Vue.extend({
  name: 'App',
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
#app {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
