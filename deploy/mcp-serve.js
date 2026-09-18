const http = require('http');
const { exec } = require('child_process');

const PORT = process.env.MCP_PORT || 3001;

process.on('uncaughtException', (e) => console.error('uncaught:', e.message));
process.on('unhandledRejection', (e) => console.error('unhandled:', e));

function runCmd(cmd, timeout) {
  return new Promise((resolve) => {
    exec(cmd, { timeout: timeout || 120000, encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error && !stdout) {
          resolve({ content: [{ type: 'text', text: (stderr || error.message) }], isError: true });
        } else {
          let text = stdout || '';
          if (error) text += (text ? '\n' : '') + '[exit ' + error.code + '] ' + (stderr || '').slice(0, 2000);
          resolve({ content: [{ type: 'text', text }] });
        }
      });
  });
}

const TOOLS = {
  nmap: {
    name: 'nmap',
    description: 'Network port scanner',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string', description: 'Target IP or hostname' },
        flags: { type: 'string', description: 'Nmap flags', default: '-sV -T4' }
      },
      required: ['target']
    },
    execute: (args) => runCmd(`nmap ${args.flags || '-sV -T4'} ${args.target}`, 300000)
  },
  masscan: {
    name: 'masscan',
    description: 'Fast port scanner',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string' },
        flags: { type: 'string', default: '-p1-65535 --rate=1000' }
      },
      required: ['target']
    },
    execute: (args) => runCmd(`masscan ${args.target} ${args.flags || '-p1-65535 --rate=1000'}`, 300000)
  },
  nuclei: {
    name: 'nuclei',
    description: 'Template-based vulnerability scanner',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string' },
        flags: { type: 'string', default: '' }
      },
      required: ['target']
    },
    execute: (args) => runCmd(`nuclei -target ${args.target} ${args.flags || ''}`, 600000)
  },
  curl: {
    name: 'curl',
    description: 'HTTP client',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string' },
        flags: { type: 'string', default: '-s -I' }
      },
      required: ['url']
    },
    execute: (args) => runCmd(`curl ${args.flags || '-s -I'} "${args.url}"`, 30000)
  },
  nxc: {
    name: 'nxc',
    description: 'NetExec - SMB/SSH/LDAP/WinRM enumeration and exploitation',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string' },
        protocol: { type: 'string', default: 'smb' },
        flags: { type: 'string', default: '' }
      },
      required: ['target']
    },
    execute: (args) => runCmd(`nxc ${args.protocol || 'smb'} ${args.target} ${args.flags || ''}`, 120000)
  },
  searchsploit: {
    name: 'searchsploit',
    description: 'Search ExploitDB for public exploits',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string' }
      },
      required: ['query']
    },
    execute: (args) => runCmd(`searchsploit ${args.query}`, 60000)
  },
  adscan: {
    name: 'adscan',
    description: 'ADscan - Active Directory pentesting and auditing',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string' },
        flags: { type: 'string', default: '' }
      },
      required: ['target']
    },
    execute: (args) => runCmd(`adscan ${args.flags || ''} ${args.target}`, 600000)
  },
  adpeas: {
    name: 'adpeas',
    description: 'adPEAS - winPEAS for Active Directory (BloodHound, Certipy, AD enumeration). Requires credentials.',
    inputSchema: {
      type: 'object',
      properties: {
        target: { type: 'string', description: 'DC IP address' },
        username: { type: 'string' },
        password: { type: 'string' },
        domain: { type: 'string' },
        flags: { type: 'string', default: '' }
      }
    },
    execute: (args) => {
      const flags = [
        args.username && `-u ${args.username}`,
        args.password && `-p ${args.password}`,
        args.domain && `-d ${args.domain}`,
        (args.dc_ip || args.target) && `-i ${args.dc_ip || args.target}`,
        args.flags || ''
      ].filter(Boolean).join(' ');
      return runCmd(`adPEAS ${flags}`, 600000);
    }
  }
};

function handleJsonRpc(body, res) {
  const { id, method, params } = body;

  switch (method) {
    case 'initialize':
      return {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: { name: 'netactor-toolbox', version: '1.0.0' }
        }
      };

    case 'notifications/initialized':
      return null;

    case 'tools/list':
      return {
        jsonrpc: '2.0',
        id,
        result: {
          tools: Object.values(TOOLS).map(t => ({
            name: t.name,
            description: t.description,
            inputSchema: t.inputSchema
          }))
        }
      };

    case 'tools/call': {
      const tool = TOOLS[params?.name];
      if (!tool) {
        return {
          jsonrpc: '2.0',
          id,
          error: { code: -32601, message: `Tool '${params?.name}' not found` }
        };
      }
      // async execution — respond when the tool finishes
      tool.execute(params.arguments || {}).then((result) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id: body.id, result }));
      }).catch((e) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          jsonrpc: '2.0', id,
          result: { content: [{ type: 'text', text: 'Tool error: ' + e.message }], isError: true }
        }));
      });
      return 'async';
    }

    default:
      return {
        jsonrpc: '2.0',
        id,
        error: { code: -32601, message: `Method '${method}' not found` }
      };
  }
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', tools: Object.keys(TOOLS) }));
    return;
  }

  if (req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', async () => {
      try {
        const request = JSON.parse(body);
        const response = handleJsonRpc(request, res);
        if (response === 'async') return; // handled asynchronously
        if (response === null) {
          res.writeHead(204);
          res.end();
          return;
        }
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(response));
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ jsonrpc: '2.0', id: null, error: { code: -32603, message: e.message } }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`MCP Toolbox server running on port ${PORT}`);
});