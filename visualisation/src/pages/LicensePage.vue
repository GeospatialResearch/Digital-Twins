<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <div class="multiline">
    {{ license }}
  </div>
</template>

<script setup lang="ts">
import license from "../../../LICENSE?raw"
import {usePageTitlePrefix} from "./composables/title";

// Add page title prefix to webpage title
usePageTitlePrefix("License");
</script>

<style scoped>
div.multiline {
  white-space: pre;
}
</style>
