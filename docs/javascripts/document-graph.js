/**
 * Document Graph Visualization
 * 
 * Renders the Core Knowledge Graph using Cytoscape.js.
 * Loads graph data from JSON and provides interactive navigation.
 */

(function() {
  'use strict';

  /**
   * Resolve URL relative to site base path
   */
  function resolveSiteUrl(path) {
    if (!path) return null;
    if (/^https?:\/\//.test(path)) return null;
    var basePath = typeof __md_scope !== 'undefined' ? __md_scope.href : '/';
    return new URL(path.replace(/^\//, ''), basePath).href;
  }

  function parseRgbColor(value) {
    var match = value && value.match(/^rgba?\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d+(?:\.\d+)?))?\s*\)$/);
    if (!match) return null;
    return {
      r: Number(match[1]),
      g: Number(match[2]),
      b: Number(match[3]),
      a: match[4] !== undefined ? Number(match[4]) : 1
    };
  }

  function resolveNodeLabelColor(container) {
    var target = container || document.body;
    if (!target || typeof window.getComputedStyle !== 'function') {
      return '#333';
    }
    var fg = parseRgbColor(window.getComputedStyle(target).color);
    if (!fg && document.body && target !== document.body) {
      fg = parseRgbColor(window.getComputedStyle(document.body).color);
    }
    if (!fg) {
      return '#333';
    }
    if (fg.a >= 1) {
      return 'rgb(' + Math.round(fg.r) + ', ' + Math.round(fg.g) + ', ' + Math.round(fg.b) + ')';
    }
    var bg = { r: 255, g: 255, b: 255 };
    var el = target;
    while (el && el.nodeType === 1) {
      var parsedBg = parseRgbColor(window.getComputedStyle(el).backgroundColor);
      if (parsedBg && parsedBg.a >= 0.99) {
        bg = parsedBg;
        break;
      }
      el = el.parentElement;
    }
    var r = Math.round(fg.r * fg.a + bg.r * (1 - fg.a));
    var g = Math.round(fg.g * fg.a + bg.g * (1 - fg.a));
    var b = Math.round(fg.b * fg.a + bg.b * (1 - fg.a));
    return 'rgb(' + r + ', ' + g + ', ' + b + ')';
  }

  function observePaletteChanges(container, cy) {
    if (typeof MutationObserver === 'undefined' || !document.body) {
      return;
    }
    var observer = new MutationObserver(function() {
      if (!container.isConnected || cy.destroyed()) {
        observer.disconnect();
        return;
      }
      cy.style().selector('node').style('color', resolveNodeLabelColor(container)).update();
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['data-md-color-scheme']
    });
  }

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

    // Load graph data
    fetch(dataUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json();
      })
      .then(data => {
        const links = document.getElementById('core-graph-links');
        const list = document.createElement('ul');
        data.elements.filter(element => !element.data.source).map(element => element.data)
          .sort((a, b) => a.label.localeCompare(b.label, 'en') || a.id.localeCompare(b.id, 'en'))
          .forEach(node => {
            const item = document.createElement('li');
            const link = document.createElement('a');
            link.href = resolveSiteUrl(node.href);
            link.textContent = node.label;
            item.append(link, ' (' + node.type.replace(/_/g, ' ') + ')');
            list.append(item);
          });
        links.append(list);
        if (typeof cytoscape === 'undefined') {
          console.warn('Cytoscape.js not loaded');
          const message = document.createElement('p');
          message.style.cssText = 'color: var(--md-default-fg-color); text-align: center; padding: 2rem;';
          message.textContent = 'The interactive graph could not be loaded because the visualization library did not load. The same destinations are listed below. ';
          const link = document.createElement('a');
          link.href = '#core-graph-links';
          link.textContent = 'Go to Core graph destinations';
          link.style.cssText = 'color: inherit; text-decoration: underline;';
          message.append(link);
          container.replaceChildren(message);
          return;
        }
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
            'color': resolveNodeLabelColor(container),
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
      userZoomingEnabled: false,
      userPanningEnabled: false,
      wheelSensitivity: 0.3
    });

    // Click to navigate
    cy.on('tap', 'node', function(evt) {
      var node = evt.target;
      var href = node.data('href') || node.data('link');
      var resolvedUrl = resolveSiteUrl(href);
      if (resolvedUrl) {
        window.location.href = resolvedUrl;
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
    observePaletteChanges(container, cy);
  }

  /**
   * Setup graph controls (search, filter, reset)
   */
  function setupControls(cy) {
    const gestures = document.createElement('button');
    gestures.type = 'button';
    gestures.className = 'graph-gestures';
    gestures.setAttribute('aria-pressed', 'false');
    gestures.setAttribute('aria-describedby', 'graph-gestures-hint');
    const gestureState = document.createElement('span');
    gestureState.setAttribute('aria-hidden', 'true');
    gestureState.textContent = ': off';
    gestures.append('Graph gestures', gestureState);
    const hint = document.createElement('span');
    hint.id = 'graph-gestures-hint';
    hint.className = 'graph-gesture-hint';
    hint.textContent = 'Turn on to zoom with the wheel or pinch and pan by dragging the background with mouse or touch. Turn off to scroll the page. Tapping nodes still opens pages. Reset View turns gestures off.';
    document.getElementById('graph-controls').append(gestures, hint);
    function setGestures(enabled) {
      cy.userZoomingEnabled(enabled);
      cy.userPanningEnabled(enabled);
      cy.container().classList.toggle('graph-gestures-enabled', enabled);
      gestures.setAttribute('aria-pressed', String(enabled));
      gestureState.textContent = enabled ? ': on' : ': off';
    }
    gestures.addEventListener('click', function() {
      setGestures(!cy.userPanningEnabled());
    });
    cy.container().addEventListener('touchstart', function(event) {
      if (!cy.userPanningEnabled()) {
        event.stopImmediatePropagation();
      }
    }, { capture: true, passive: true });
    document.addEventListener('gesturestart', function(event) {
      if (!cy.userPanningEnabled() && cy.container().contains(event.target)) {
        event.stopImmediatePropagation();
      }
    }, { capture: true, passive: true });

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
        setGestures(false);
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
