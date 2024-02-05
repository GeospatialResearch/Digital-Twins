<template>
  <!-- Page displaying About information. Context of the web app, license, source code, etc.  -->
  <b-container fluid>
    <h3>Flood Resilience Digital Twin (FReDT)</h3>
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

export default Vue.extend({
  name: "AboutPage",
  title: "About",
  mixins: [titleMixin],
  data() {
    return {
      license: "MIT License\n" +
        "\n" +
        "© Copyright 2023 Geospatial Research Institute Toi Hangarau\n" +
        "\n" +
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n" +
        "of this software and associated documentation files (the \"Software\"), to deal\n" +
        "in the Software without restriction, including without limitation the rights\n" +
        "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n" +
        "copies of the Software, and to permit persons to whom the Software is\n" +
        "furnished to do so, subject to the following conditions:\n" +
        "\n" +
        "The above copyright notice and this permission notice shall be included in all\n" +
        "copies or substantial portions of the Software.\n" +
        "\n" +
        "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n" +
        "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n" +
        "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n" +
        "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n" +
        "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n" +
        "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n" +
        "SOFTWARE.\n"
    }
  }
});
</script>

<style scoped>
div.multiline {
  white-space: pre;
}
</style>
