// Deterministic implementation of all nine graph-reviewer.md checks.
const fs = require('node:fs');
const path = require('node:path');
try {
  const graph = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const issues = [], warnings = [];
  const types = new Set('file function class module concept config document service table endpoint pipeline schema resource domain flow step'.split(' '));
  const edgeTypes = new Set('imports exports contains inherits implements calls subscribes publishes middleware reads_from writes_to transforms validates depends_on tested_by configures related similar_to deploys serves migrates documents provisions routes defines_schema triggers contains_flow flow_step cross_domain'.split(' '));
  const fileTypes = new Set('file config document service pipeline table schema resource endpoint'.split(' '));
  const collection = (key) => {
    if (!Array.isArray(graph[key])) { issues.push(`${key} must be an array`); return []; }
    return graph[key];
  };
  const nodes = collection('nodes'), edges = collection('edges'), layers = collection('layers'), tour = collection('tour');
  const nonempty = value => typeof value === 'string' && value.trim().length > 0;
  const ids = new Set(nodes.map(n => n?.id).filter(nonempty));
  const idIndices = new Map(), degree = new Map(), connectedTypes = new Map(), layerCount = new Map();
  const counts = (values) => Object.fromEntries([...new Set(values)].sort().map(value => [String(value), values.filter(x => x === value).length]));
  const domain = nodes.some(n => ['domain', 'flow', 'step'].includes(n?.type));
  // Checks 1, 5, 7 and 9: node fields, IDs, summary quality and prefix.
  nodes.forEach((node, index) => {
    if (!node || typeof node !== 'object' || Array.isArray(node)) { issues.push(`Node at index ${index} must be an object`); return; }
    const ref = `Node at index ${index} (${JSON.stringify(node.id)})`;
    if (!nonempty(node.id) || ![...types].some(t => node.id.startsWith(`${t}:`) && node.id.length > t.length + 1)) issues.push(`${ref} has invalid or missing id prefix`);
    if (!types.has(node.type)) issues.push(`${ref} has invalid or missing type ${JSON.stringify(node.type)}`);
    if (!nonempty(node.name)) issues.push(`${ref} has invalid or missing name`);
    const filename = typeof node.filePath === 'string' ? path.posix.basename(node.filePath.replaceAll('\\', '/')) : (typeof node.name === 'string' ? path.posix.basename(node.name.replaceAll('\\', '/')) : undefined);
    const generic = !nonempty(node.summary) || node.summary.trim() === node.name || node.summary.trim() === filename;
    if (generic) { issues.push(`${ref} summary is empty or just restates the name/filename`); warnings.push(`${ref} has an empty or filename-only summary`); }
    else if (node.summary.trim().length < 20) warnings.push(`${ref} has a short summary (under 20 characters)`);
    if (!Array.isArray(node.tags) || node.tags.length === 0 || node.tags.some(t => typeof t !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(t))) issues.push(`${ref} tags must contain at least one lowercase hyphenated string`);
    if (!['simple', 'moderate', 'complex'].includes(node.complexity)) issues.push(`${ref} has invalid or missing complexity`);
    if (nonempty(node.id) && types.has(node.type) && !node.id.startsWith(`${node.type}:`)) warnings.push(`${ref} type '${node.type}' does not match ID prefix`);
    if (!idIndices.has(node.id)) idIndices.set(node.id, []);
    idIndices.get(node.id).push(index);
  });
  for (const [id, indices] of idIndices) if (indices.length > 1) issues.push(`Duplicate node ID ${JSON.stringify(id)} at indices ${indices.join(', ')}`);
  // Checks 1, 2 and 7: all edge fields and every dangling endpoint.
  edges.forEach((edge, index) => {
    if (!edge || typeof edge !== 'object' || Array.isArray(edge)) { issues.push(`Edge at index ${index} must be an object`); return; }
    for (const endpoint of ['source', 'target']) {
      if (!nonempty(edge[endpoint])) issues.push(`Edge at index ${index} has invalid or missing ${endpoint}`);
      else if (!ids.has(edge[endpoint])) issues.push(`Edge at index ${index} references non-existent ${endpoint} node '${edge[endpoint]}'`);
      else {
        degree.set(edge[endpoint], (degree.get(edge[endpoint]) || 0) + 1);
        if (!connectedTypes.has(edge[endpoint])) connectedTypes.set(edge[endpoint], new Set());
        connectedTypes.get(edge[endpoint]).add(edge.type);
      }
    }
    if (!edgeTypes.has(edge.type)) issues.push(`Edge at index ${index} has invalid or missing type ${JSON.stringify(edge.type)}`);
    if (!['forward', 'backward', 'bidirectional'].includes(edge.direction)) issues.push(`Edge at index ${index} has invalid or missing direction`);
    if (typeof edge.weight !== 'number' || !Number.isFinite(edge.weight) || edge.weight < 0 || edge.weight > 1) issues.push(`Edge at index ${index} weight must be a finite number between 0 and 1`);
    if (nonempty(edge.source) && edge.source === edge.target) warnings.push(`Edge at index ${index} self-references '${edge.source}'`);
  });
  // Checks 2, 4 and 6: layer/tour references and membership.
  const checkRefs = (item, index, kind) => {
    const label = `${kind} at index ${index} (${JSON.stringify(item?.id ?? item?.title)})`;
    if (!Array.isArray(item?.nodeIds)) { issues.push(`${label} nodeIds must be an array`); return []; }
    item.nodeIds.forEach((id, i) => { if (!ids.has(id)) issues.push(`${label} nodeIds[${i}] references non-existent node ${JSON.stringify(id)}`); });
    return item.nodeIds;
  };
  layers.forEach((layer, index) => {
    const members = checkRefs(layer, index, 'Layer');
    if (members.length === 0) issues.push(`Layer at index ${index} (${JSON.stringify(layer?.id)}) has empty nodeIds`);
    for (const id of new Set(members)) layerCount.set(id, (layerCount.get(id) || 0) + 1);
  });
  if (!(domain && layers.length === 0)) for (const node of nodes) if (fileTypes.has(node?.type)) {
    const count = layerCount.get(node.id) || 0;
    if (count !== 1) issues.push(`File-level node '${node.id}' appears in ${count} layers; exactly one required`);
  }
  const orders = new Map();
  tour.forEach((step, index) => {
    const members = checkRefs(step, index, 'Tour step');
    if (members.length === 0) warnings.push(`Tour step at index ${index} has no nodeIds`);
    if (step?.order !== index + 1) warnings.push(`Tour step at index ${index} has order ${JSON.stringify(step?.order)}; expected ${index + 1}`);
    if (orders.has(step?.order)) warnings.push(`Duplicate tour order ${JSON.stringify(step?.order)} at indices ${orders.get(step?.order)} and ${index}`);
    else orders.set(step?.order, index);
  });
  if (tour.length < 5 || tour.length > 15) warnings.push(`Tour has ${tour.length} steps; expected 5 to 15`);
  // Check 3: domain relaxation is applied only to missing layers/tour.
  if (!nodes.length) issues.push('Graph has zero nodes');
  if (!edges.length) issues.push('Graph has zero edges');
  for (const [label, list] of [['layers', layers], ['tour steps', tour]]) if (!list.length) (domain ? warnings : issues).push(`Graph has zero ${label}${domain ? ' (domain graph)' : ''}`);
  // Checks 7 and 8: orphans and only the specified, clear relationships.
  const expected = {document:['documents'], service:['deploys','depends_on'], pipeline:['triggers'], table:['migrates','defines_schema'], schema:['defines_schema'], domain:['contains_flow'], flow:['flow_step']};
  for (const node of nodes) {
    if (!degree.get(node?.id)) warnings.push(`Node '${node?.id}' has no edges connecting to it`);
    const required = expected[node?.type];
    if (required && !required.some(t => connectedTypes.get(node.id)?.has(t))) warnings.push(`${node.type} node '${node.id}' has no '${required.join("' or '")}' edges`);
  }
  const result = {scriptCompleted:true, issues, warnings, stats:{totalNodes:nodes.length,totalEdges:edges.length,totalLayers:layers.length,tourSteps:tour.length,nodeTypes:counts(nodes.map(n=>n?.type)),edgeTypes:counts(edges.map(e=>e?.type))}};
  fs.writeFileSync(process.argv[3], JSON.stringify(result, null, 2) + '\n');
  process.exitCode = 0;
} catch (error) { console.error(error.stack || String(error)); process.exitCode = 1; }
