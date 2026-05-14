<script setup>
import { RouterLink, RouterView, useRoute } from 'vue-router'
import logo from './assets/logo.svg'

const route = useRoute()

const navItems = [
  { label: 'Головна', to: '/' },
  { label: 'Історія', to: '/history' },
]
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="container header-inner">
        <RouterLink to="/" class="brand-link">
          <img :src="logo" alt="xenlo" class="brand-logo" />
        </RouterLink>

        <nav class="header-nav">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            :class="{ 'nav-link-active': route.path === item.to }"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="site-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--app-border);
}

.header-inner {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand-link {
  display: inline-flex;
  align-items: center;
}

.brand-logo {
  height: 34px;
  width: auto;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.nav-link {
  padding: 10px 14px;
  border-radius: 10px;
  color: var(--app-text-muted);
  font-size: 14px;
  font-weight: 500;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

.nav-link:hover {
  background: var(--app-surface-soft);
  color: var(--app-text);
}

.nav-link-active {
  background: #eef2ff;
  color: var(--app-primary);
}

.site-main {
  padding-block: 40px 72px;
}
</style>
