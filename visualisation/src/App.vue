<template>
  <div id="app">
    <MapViewer
      class="full-screen-map"
      :init-lat="kaiapoi.latitude"
      :init-long="kaiapoi.longitude"
      :token="hereApiToken"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue';
import {MapViewer} from 'geo-visualisation-components/src/components';

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
      hereApiToken: process.env.VUE_APP_HEREAPI,
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
