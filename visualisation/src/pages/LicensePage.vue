<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <div class="multiline">
    {{ license }}
  </div>
</template>

<script lang="ts">
import Vue from "vue";
import titleMixin from "@/mixins/title"
import license from "../../../LICENSE"

export default Vue.extend({
  name: "LicensePage",
  title: "License",
  mixins: [titleMixin],
  data() {
    return {
      license: license
    }
  },
});
</script>

<style scoped>
div.multiline {
  white-space: pre;
}
</style>
