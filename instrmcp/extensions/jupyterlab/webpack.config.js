// Custom webpack configuration for mcp-active-cell-bridge
// Produces clean, readable chunk names instead of numeric IDs or verbose paths

module.exports = {
  output: {
    // Custom chunk filename with cleaner names
    chunkFilename: (pathData) => {
      const name = pathData.chunk.name || pathData.chunk.id;

      // Map verbose names to clean ones
      if (name.includes('node_modules_diff')) return 'vendors-diff.[contenthash].js';
      if (name.includes('lib_index')) return 'index.[contenthash].js';
      if (name.includes('style_index')) return 'styles.[contenthash].js';

      // Fallback: shorten the name
      const shortName = name
        .replace(/node_modules_/g, '')
        .replace(/_libesm_index_js/g, '')
        .replace(/_index_js/g, '')
        .replace(/_index_css/g, '')
        .replace(/^lib_/, '');

      return `${shortName}.[contenthash].js`;
    },
  },
  optimization: {
    chunkIds: 'named',
  },
};
