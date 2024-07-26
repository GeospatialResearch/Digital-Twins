<template>
  <!-- The Vue app main context -->
  <div id="app">
    <TheNavBar />
    <router-view ref="routerView" />
  </div>
</template>

<script lang="ts">
import {defineComponent} from 'vue';
import TheNavBar from "@/components/TheNavBar.vue";

export default defineComponent({
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
