<template>
  <!-- The Vue app main context -->
  <div id="app">
    <TheNavBar />
    <b-container fluid>
      <router-view ref="routerView" />
    </b-container>
  </div>
</template>

<script lang="ts">
import Vue from 'vue';
import TheNavBar from "@/components/TheNavBar.vue";

export default Vue.extend({
  name: 'App',
  components: {TheNavBar},
});
</script>

<style>
#app {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
