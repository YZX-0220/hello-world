<template>
  <router-view />
</template>

<style>
/* 全局重置与基准字体放大 */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}
html {
  /* 调大根字号，让 rem 和基础文字更加清晰 */
  font-size: 16px;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
  background-color: #0c0f17;
  color: #f1f5f9;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>