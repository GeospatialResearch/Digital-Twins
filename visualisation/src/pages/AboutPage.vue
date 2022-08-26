<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <b-container fluid>
    <h3>Digital Twin for Flood Resilience</h3>
    <p>
      This web application visualises and provides controls to the Digital Twin for Flood Resilience in New Zealand
    </p>
    <p>&nbsp;</p>
    <hr>
    <h4>Source code</h4>
    <p>
      The source code for the app <a href="https://github.com/GeospatialResearch/Digital-Twins">can be obtained from
        GitHub here</a>.
    </p>
    <hr>
    <h4>App licence</h4>
    <div class="multiline">
      {{ license }}
    </div>
  </b-container>
</template>

<script lang="ts">
import Vue from "vue";
import titleMixin from "@/mixins/title"
import licenseText from "@/../../LICENSE";

export default Vue.extend({
  name: "AboutPage",
  title: "About",
  mixins: [titleMixin],
  data() {
    return {
      license: licenseText
    }
  }
});
</script>

<style scoped>
div.multiline {
  white-space: pre;
}
</style>
