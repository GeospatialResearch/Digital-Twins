<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <b-container fluid>
    <h3>Flood Resilience Digital Twin (FReDT)</h3>
    <p>
      This web application visualises and provides controls to the Digital Twin for Flood Resilience in New Zealand.
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
    <p>
      The code license for this particular version of the code can be found on our
      <router-link :to="{ name: 'License'}">License Page</router-link>.
    </p>
  </b-container>
</template>

<script lang="ts">
import {RouterLink} from "vue-router";
import Vue from "vue";
import titleMixin from "@/mixins/title"

export default Vue.extend({
  name: "AboutPage",
  title: "About",
  components: {
    RouterLink,
  },
  mixins: [titleMixin],
});
</script>
