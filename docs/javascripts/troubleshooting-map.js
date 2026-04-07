/**
 * Troubleshooting Map Visualization
 * 
 * Renders the troubleshooting-specific graph using Cytoscape.js.
 * Focuses on playbooks, labs, KQL queries, and their relationships.
 */

(function() {
  'use strict';

  // Node type colors (troubleshooting-focused palette)
  const NODE_COLORS = {
    playbook: '#f57c00',      // Orange - Main playbooks
    lab: '#d32f2f',           // Red - Labs that validate
    kql: '#7b1fa2',           // Purple - KQL queries
    map: '#00796b',           // Teal - Decision trees, guides
    symptom: '#e91e63',       // Pink - Entry symptoms
    first_10: '#ff9800',      // Amber - First 10 minutes guides
    methodology: '#607d8b'    // Blue-gray - Methodology docs
  };

  // Category colors for grouping
  const CATEGORY_COLORS = {
    startup: '#2196f3',       // Blue
    performance: '#ff5722',   // Deep orange
    network: '#4caf50'        // Green
  };

  // Edge relationship styles
  const EDGE_STYLES = {
    validated_by_lab: { lineStyle: 'solid', lineColor: '#388e3c', width: 2.5 },
    investigated_with_kql: { lineStyle: 'dashed', lineColor: '#7b1fa2', width: 2 },
    guided_by_map: { lineStyle: 'dotted', lineColor: '#00796b', width: 1.5 },
    symptom_to_playbook: { lineStyle: 'solid', lineColor: '#f57c00', width: 3 },
    prerequisite: { lineStyle: 'solid', lineColor: '#9e9e9e', width: 1.5 },
    related: { lineStyle: 'dashed', lineColor: '#bdbdbd', width: 1 }
  };

  /**
   * Initialize the Troubleshooting Map
   * @param {string} containerId - DOM element ID for the graph container
   * @param {string} dataUrl - URL to the troubleshooting graph JSON data
   */
  window.initTroubleshootingMap = function(containerId, dataUrl) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.warn('Troubleshooting map container not found:', containerId);
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
        renderTroubleshootingMap(container, data);
      })
      .catch(error => {
        console.warn('Failed to load troubleshooting map data:', error);
        container.innerHTML = `
          <p style="color: var(--md-default-fg-color--light); text-align: center; padding: 2rem;">
            Troubleshooting map data not yet generated.<br>
            Run <code>python tools/build_troubleshooting_map.py</code> to generate.
          </p>
        `;
      });
  };

  /**
   * Render the troubleshooting map
   */
  function renderTroubleshootingMap(container, data) {
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
            'text-margin-y': 6,
            'font-size': '12px',
            'font-family': 'var(--md-text-font-family, Roboto, sans-serif)',
            'color': 'var(--md-default-fg-color, #333)',
            'text-max-width': '120px',
            'text-wrap': 'ellipsis',
            'width': 35,
            'height': 35,
            'border-width': 3,
            'border-color': '#fff',
            'shape': 'ellipse'
          }
        },
        
        // Node type-specific styles
        ...Object.entries(NODE_COLORS).map(([type, color]) => ({
          selector: `node[type="${type}"]`,
          style: {
            'background-color': color,
            'border-color': color
          }
        })),

        // Playbook nodes are larger
        {
          selector: 'node[type="playbook"]',
          style: {
            'width': 45,
            'height': 45,
            'font-weight': 'bold'
          }
        },

        // Lab nodes have diamond shape
        {
          selector: 'node[type="lab"]',
          style: {
            'shape': 'diamond'
          }
        },

        // KQL nodes have hexagon shape
        {
          selector: 'node[type="kql"]',
          style: {
            'shape': 'hexagon'
          }
        },

        // Map nodes have rectangle shape
        {
          selector: 'node[type="map"]',
          style: {
            'shape': 'round-rectangle',
            'width': 50,
            'height': 30
          }
        },

        // Category border colors
        {
          selector: 'node[category="startup"]',
          style: {
            'border-color': CATEGORY_COLORS.startup,
            'border-width': 4
          }
        },
        {
          selector: 'node[category="performance"]',
          style: {
            'border-color': CATEGORY_COLORS.performance,
            'border-width': 4
          }
        },
        {
          selector: 'node[category="network"]',
          style: {
            'border-color': CATEGORY_COLORS.network,
            'border-width': 4
          }
        },

        // Edge base style
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': '#bdbdbd',
            'target-arrow-color': '#bdbdbd',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.9
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
            'border-width': 5,
            'border-color': '#212121',
            'z-index': 999
          }
        },

        // Selected state
        {
          selector: 'node:selected',
          style: {
            'border-width': 5,
            'border-color': '#ff5722',
            'background-blacken': -0.15
          }
        },

        // Highlighted (search/filter match)
        {
          selector: '.highlighted',
          style: {
            'border-width': 5,
            'border-color': '#ffeb3b',
            'background-blacken': -0.2
          }
        },

        // Dimmed (non-matching)
        {
          selector: '.dimmed',
          style: {
            'opacity': 0.25
          }
        },

        // Connected edges when node is selected
        {
          selector: 'node:selected ~ edge',
          style: {
            'opacity': 1,
            'width': 3
          }
        }
      ],

      layout: {
        name: 'cose',
        idealEdgeLength: 120,
        nodeOverlap: 30,
        refresh: 20,
        fit: true,
        padding: 40,
        randomize: false,
        componentSpacing: 150,
        nodeRepulsion: 500000,
        edgeElasticity: 80,
        nestingFactor: 5,
        gravity: 100,
        numIter: 1500,
        initialTemp: 250,
        coolingFactor: 0.95,
        minTemp: 1.0
      },

      // Interaction options
      minZoom: 0.2,
      maxZoom: 4,
      wheelSensitivity: 0.25
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
      updateTsInfoPanel(node);
    });

    cy.on('unselect', 'node', function() {
      clearTsInfoPanel();
    });

    // Setup controls
    setupTsControls(cy);
  }

  /**
   * Setup troubleshooting map controls
   */
  function setupTsControls(cy) {
    // Search
    const searchInput = document.getElementById('ts-search');
    if (searchInput) {
      searchInput.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        
        if (!query) {
          cy.elements().removeClass('highlighted dimmed');
          return;
        }

        cy.nodes().forEach(node => {
          const label = (node.data('label') || '').toLowerCase();
          const topics = (node.data('topics') || []).join(' ').toLowerCase();
          const category = (node.data('category') || '').toLowerCase();
          
          const matches = label.includes(query) || topics.includes(query) || category.includes(query);
          
          if (matches) {
            node.removeClass('dimmed').addClass('highlighted');
          } else {
            node.removeClass('highlighted').addClass('dimmed');
          }
        });

        cy.edges().addClass('dimmed');
      });
    }

    // Filter by category
    const categorySelect = document.getElementById('ts-category');
    if (categorySelect) {
      categorySelect.addEventListener('change', function() {
        const category = this.value;
        filterByAttribute(cy, 'category', category);
      });
    }

    // Filter by type
    const typeSelect = document.getElementById('ts-type');
    if (typeSelect) {
      typeSelect.addEventListener('change', function() {
        const type = this.value;
        filterByAttribute(cy, 'type', type);
      });
    }

    // Reset view
    const resetButton = document.getElementById('ts-reset');
    if (resetButton) {
      resetButton.addEventListener('click', function() {
        cy.elements().removeClass('highlighted dimmed');
        cy.fit();
        
        if (searchInput) searchInput.value = '';
        if (categorySelect) categorySelect.value = 'all';
        if (typeSelect) typeSelect.value = 'all';
        
        clearTsInfoPanel();
      });
    }
  }

  /**
   * Filter nodes by attribute
   */
  function filterByAttribute(cy, attr, value) {
    if (value === 'all') {
      cy.elements().removeClass('dimmed highlighted');
      return;
    }

    cy.nodes().forEach(node => {
      if (node.data(attr) === value) {
        node.removeClass('dimmed').addClass('highlighted');
      } else {
        node.removeClass('highlighted').addClass('dimmed');
      }
    });

    cy.edges().addClass('dimmed');
  }

  /**
   * Update troubleshooting info panel
   */
  function updateTsInfoPanel(node) {
    const selectedSpan = document.getElementById('ts-selected-node');
    const categorySpan = document.getElementById('ts-node-category');
    const evidenceSpan = document.getElementById('ts-node-evidence');

    if (selectedSpan) {
      selectedSpan.textContent = node.data('label') || node.id();
    }

    if (categorySpan) {
      categorySpan.textContent = node.data('category') || '-';
    }

    if (evidenceSpan) {
      const evidence = node.data('evidence') || [];
      evidenceSpan.textContent = evidence.length > 0 ? evidence.join(', ') : '-';
    }
  }

  /**
   * Clear troubleshooting info panel
   */
  function clearTsInfoPanel() {
    const selectedSpan = document.getElementById('ts-selected-node');
    const categorySpan = document.getElementById('ts-node-category');
    const evidenceSpan = document.getElementById('ts-node-evidence');

    if (selectedSpan) selectedSpan.textContent = 'None';
    if (categorySpan) categorySpan.textContent = '-';
    if (evidenceSpan) evidenceSpan.textContent = '-';
  }

})();
