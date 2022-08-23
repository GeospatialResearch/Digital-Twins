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
    <p>
      &#169; Copyright 2021 Matt Wilson/Geospatial Research Institute Toi Hangarau
    </p>
    <p>
      Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
      documentation files (the "Software"), to deal in the Software without restriction, including without limitation
      the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
      to permit persons to whom the Software is furnished to do so, subject to the following conditions:
    </p>
    <p>
      The above copyright notice and this permission notice shall be included in all copies or substantial portions of
      the Software.
    </p>
    <p>
      THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, E
      XPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
      THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
      AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
      CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
      IN THE SOFTWARE.
    </p>
  </b-container>
</template>

<script lang="ts">
import Vue from "vue";

export default Vue.extend({
  name: "AboutPage",
  title: "About",
});
</script>

<style scoped>

</style>
