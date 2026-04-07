/**
 * Document Graph Visualization
 * 
 * Renders the Core Knowledge Graph using Cytoscape.js.
 * Loads graph data from JSON and provides interactive navigation.
 */

(function() {
  'use strict';

  // Node type colors (matching Material theme)
  const NODE_COLORS = {
    concept: '#1976d2',       // Blue - Platform concepts
    best_practice: '#388e3c', // Green - Best practices
    playbook: '#f57c00',      // Orange - Troubleshooting playbooks
    lab: '#d32f2f',           // Red - Hands-on labs
    kql: '#7b1fa2',           // Purple - KQL queries
    map: '#00796b',           // Teal - Decision trees, evidence maps
    reference: '#616161',     // Gray - Reference docs
    tutorial: '#0288d1',      // Light blue - Tutorials
    operation: '#5d4037'      // Brown - Operations
  };

  // Edge type styles
  const EDGE_STYLES = {
    prerequisite: { lineStyle: 'solid', lineColor: '#9e9e9e', width: 2 },
    related: { lineStyle: 'dashed', lineColor: '#9e9e9e', width: 1.5 },
    used_in: { lineStyle: 'dotted', lineColor: '#9e9e9e', width: 1.5 },
    deep_dive_for: { lineStyle: 'solid', lineColor: '#1976d2', width: 2 },
    troubleshooting_for: { lineStyle: 'solid', lineColor: '#f57c00', width: 2 },
    validated_by_lab: { lineStyle: 'solid', lineColor: '#388e3c', width: 2 },
    investigated_with_kql: { lineStyle: 'dashed', lineColor: '#7b1fa2', width: 1.5 }
  };

  /**
   * Initialize the Core Knowledge Graph
   * @param {string} containerId - DOM element ID for the graph container
   * @param {string} dataUrl - URL to the graph JSON data
   */
  window.initCoreKnowledgeGraph = function(containerId, dataUrl) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.warn('Graph container not found:', containerId);
      return;
    }

    // Check if Cytoscape is loaded
    if (typeof cytoscape === 'undefined') {
      console.warn('Cytoscape.js not loaded');
      container.innerHTML = '<p style="color: var(--md-default-fg-color--light); text-align: center; padding: 2rem;">Loading visualization library...</p>';
      return;
    }

    // Load graph data
    fetch(dataUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        renderGraph(container, data);
      })
      .catch(error => {
        console.warn('Failed to load graph data:', error);
        container.innerHTML = `
          <p style="color: var(--md-default-fg-color--light); text-align: center; padding: 2rem;">
            Graph data not yet generated.<br>
            Run <code>python tools/build_doc_graph.py</code> to generate.
          </p>
        `;
      });
  };

  /**
   * Render the graph using Cytoscape.js
   */
  function renderGraph(container, data) {
    const cy = cytoscape({
      container: container,
      elements: data.elements || [],
      
      style: [
        // Node base style
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 5,
            'font-size': '11px',
            'font-family': 'var(--md-text-font-family, Roboto, sans-serif)',
            'color': 'var(--md-default-fg-color, #333)',
            'text-max-width': '100px',
            'text-wrap': 'ellipsis',
            'width': 30,
            'height': 30,
            'border-width': 2,
            'border-color': '#fff'
          }
        },
        
        // Node type-specific colors
        ...Object.entries(NODE_COLORS).map(([type, color]) => ({
          selector: `node[type="${type}"]`,
          style: {
            'background-color': color,
            'border-color': color
          }
        })),

        // Default node color for unknown types
        {
          selector: 'node[!type]',
          style: {
            'background-color': '#9e9e9e',
            'border-color': '#9e9e9e'
          }
        },

        // Edge base style
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#bdbdbd',
            'target-arrow-color': '#bdbdbd',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8
          }
        },

        // Edge type-specific styles
        ...Object.entries(EDGE_STYLES).map(([type, style]) => ({
          selector: `edge[type="${type}"]`,
          style: {
            'line-style': style.lineStyle,
            'line-color': style.lineColor,
            'target-arrow-color': style.lineColor,
            'width': style.width
          }
        })),

        // Hover states
        {
          selector: 'node:hover',
          style: {
            'border-width': 3,
            'border-color': '#000',
            'z-index': 999
          }
        },

        // Selected state
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#ff5722',
            'background-blacken': -0.1
          }
        },

        // Highlighted (search match)
        {
          selector: '.highlighted',
          style: {
            'border-width': 4,
            'border-color': '#ff9800',
            'background-blacken': -0.2
          }
        },

        // Dimmed (non-matching in search)
        {
          selector: '.dimmed',
          style: {
            'opacity': 0.3
          }
        }
      ],

      layout: {
        name: 'cose',
        idealEdgeLength: 100,
        nodeOverlap: 20,
        refresh: 20,
        fit: true,
        padding: 30,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: 400000,
        edgeElasticity: 100,
        nestingFactor: 5,
        gravity: 80,
        numIter: 1000,
        initialTemp: 200,
        coolingFactor: 0.95,
        minTemp: 1.0
      },

      // Interaction options
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3
    });

    // Click to navigate
    cy.on('tap', 'node', function(evt) {
      const node = evt.target;
      const href = node.data('href') || node.data('link');
      if (href) {
        window.location.href = href;
      }
    });

    // Update info panel on selection
    cy.on('select', 'node', function(evt) {
      const node = evt.target;
      updateInfoPanel(node);
    });

    cy.on('unselect', 'node', function() {
      clearInfoPanel();
    });

    // Setup controls
    setupControls(cy);
  }

  /**
   * Setup graph controls (search, filter, reset)
   */
  function setupControls(cy) {
    // Search
    const searchInput = document.getElementById('graph-search');
    if (searchInput) {
      searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        
        if (!query) {
          cy.elements().removeClass('highlighted dimmed');
          return;
        }

        cy.nodes().forEach(node => {
          const label = (node.data('label') || '').toLowerCase();
          const type = (node.data('type') || '').toLowerCase();
          const topics = (node.data('topics') || []).join(' ').toLowerCase();
          
          const matches = label.includes(query) || type.includes(query) || topics.includes(query);
          
          if (matches) {
            node.removeClass('dimmed').addClass('highlighted');
          } else {
            node.removeClass('highlighted').addClass('dimmed');
          }
        });

        cy.edges().addClass('dimmed');
      });
    }

    // Filter by type
    const filterSelect = document.getElementById('graph-filter');
    if (filterSelect) {
      filterSelect.addEventListener('change', function() {
        const type = this.value;
        
        if (type === 'all') {
          cy.elements().removeClass('dimmed highlighted');
          return;
        }

        cy.nodes().forEach(node => {
          if (node.data('type') === type) {
            node.removeClass('dimmed').addClass('highlighted');
          } else {
            node.removeClass('highlighted').addClass('dimmed');
          }
        });

        cy.edges().addClass('dimmed');
      });
    }

    // Reset view
    const resetButton = document.getElementById('graph-reset');
    if (resetButton) {
      resetButton.addEventListener('click', function() {
        cy.elements().removeClass('highlighted dimmed');
        cy.fit();
        
        if (searchInput) searchInput.value = '';
        if (filterSelect) filterSelect.value = 'all';
        
        clearInfoPanel();
      });
    }
  }

  /**
   * Update info panel with selected node details
   */
  function updateInfoPanel(node) {
    const selectedSpan = document.getElementById('selected-node');
    const connectionsSpan = document.getElementById('node-connections');

    if (selectedSpan) {
      selectedSpan.textContent = node.data('label') || node.id();
    }

    if (connectionsSpan) {
      const incoming = node.incomers('edge').length;
      const outgoing = node.outgoers('edge').length;
      connectionsSpan.textContent = `${incoming} incoming, ${outgoing} outgoing`;
    }
  }

  /**
   * Clear info panel
   */
  function clearInfoPanel() {
    const selectedSpan = document.getElementById('selected-node');
    const connectionsSpan = document.getElementById('node-connections');

    if (selectedSpan) selectedSpan.textContent = 'None';
    if (connectionsSpan) connectionsSpan.textContent = '-';
  }

})();
