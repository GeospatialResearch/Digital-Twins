<template>
  <!-- Navigation Bar to allow switching between different pages in the app -->
  <nav class="navbar navbar-expand-lg navbar-light bg-light">
    <div class="container-fluid">
      <router-link class="navbar-brand" :to="{name: 'Map'}">
        Flood Resilience Digital Twin
      </router-link>
      <button class="navbar-toggler"
              type="button"
              data-bs-toggle="collapse"
              data-bs-target="#navbarText"
              aria-controls="navbarText"
              aria-expanded="false"
              aria-label="Toggle navigation"
      >
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="navbarText">
        <ul class="navbar-nav me-auto mb-2 mb-lg-0">
          <li class="nav-item">
            <router-link class="nav-link" :to="{name: 'Map'}">
              Map
            </router-link>
          </li>
          <li class="nav-item">
            <router-link class="nav-link" :to="{name: 'About'}">
              About
            </router-link>
          </li>
          <li class="nav-item">
            <router-link class="nav-link" :to="{name: 'License'}">
              License
            </router-link>
          </li>
        </ul>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">

</script>

<style scoped>

</style>
