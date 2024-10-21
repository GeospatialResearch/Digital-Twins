<template>
  <!-- The Vue app main context -->
  <div id="app">
    <TheNavBar />
    <router-view ref="routerView" />
  </div>
</template>

<script setup lang="ts">
import TheNavBar from "@/components/TheNavBar.vue";
</script>

<style>
#app {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
