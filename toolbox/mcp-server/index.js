const express = require('express');
const cors = require('cors');
const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 3001;

// Available tools
const TOOLS = {
  nmap: {
    name: 'nmap',
    description: 'Network exploration, port scanning and service detection',
    command: (args) => `nmap ${args.flags || '-sV'} ${args.target}`
  },
  masscan: {
    name: 'masscan',
    description: 'Fast port scanner for large networks',
    command: (args) => `masscan ${args.target} ${args.flags || '-p1-1000 --rate=1000'}`
  },
  nxc: {
    name: 'nxc',
    description: 'NetExec - network enumeration and exploitation (SMB, LDAP, WinRM, SSH, etc.)',
    command: (args) => `nxc ${args.protocol || 'smb'} ${args.target} ${args.flags || ''}`
  },
  searchsploit: {
    name: 'searchsploit',
    description: 'Search ExploitDB for public exploits',
    command: (args) => `searchsploit ${args.query}`
  },
  adscan: {
    name: 'adscan',
    description: 'Active Directory pentesting and auditing tool',
    command: (args) => `adscan ${args.flags || ''} ${args.target}`
  },
  adpeas: {
    name: 'adpeas',
    description: 'adPEAS - winPEAS for Active Directory. Automated AD enumeration: runs BloodHound collection, Certipy (ADCS misconfigs), domain info, users, groups, shares, GPO, delegation attacks. Requires credentials.',
    command: (args) => {
      const flags = [
        args.username && `-u ${args.username}`,
        args.password && `-p ${args.password}`,
        args.domain && `-d ${args.domain}`,
        (args.dc_ip || args.target) && `-i ${args.dc_ip || args.target}`,
        args.flags || ''
      ].filter(Boolean).join(' ');
      return `adPEAS ${flags}`;
    }
  },
  nuclei: {
    name: 'nuclei',
    description: 'Nuclei - template-based vulnerability scanner (9000+ templates: CVEs, RCE, SSRF, default creds). Use AFTER discovering open ports. Supports http, network (tcp://), ssl, dns targets.',
    command: (args) => {
      let target = args.url || args.target || '';
      // network protocol targets need tcp:// scheme
      if (args.protocol === 'network' || (args.port && !args.url)) {
        target = `tcp://${target.includes(':') ? target : `${target}:${args.port}`}`;
      } else if (args.url && args.url.startsWith('http') === false) {
        target = `https://${args.url}`;
      }
      const flags = [
        args.severity && `-severity ${args.severity}`,
        args.tags && `-tags ${args.tags}`,
        args.templates && `-t ${args.templates}`,
        !args.flags?.includes('-silent') && '-silent',
        args.flags || ''
      ].filter(Boolean).join(' ');
      return `nuclei -u ${target} ${flags}`;
    }
  },
  curl: {
    name: 'curl',
    description: 'HTTP request tool',
    command: (args) => `curl -s ${args.flags || ''} "${args.url}"`
  }
};

// Execute command
function executeCommand(command, timeout = 60000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();
    let stdout = '';
    let stderr = '';

    const parts = command.match(/(?:[^\s"]+|"[^"]*")+/g) || [command];
    const cmd = parts[0];
    const args = parts.slice(1).map(a => a.replace(/^"|"$/g, ''));

    const proc = spawn(cmd, args, { 
      shell: true,
      timeout: timeout
    });

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      resolve({
        stdout,
        stderr,
        return_code: code,
        success: code === 0,
        duration_ms: Date.now() - startTime
      });
    });

    proc.on('error', (err) => {
      resolve({
        stdout: '',
        stderr: err.message,
        return_code: -1,
        success: false,
        duration_ms: Date.now() - startTime
      });
    });
  });
}

// MCP Protocol endpoint
app.post('/mcp', async (req, res) => {
  const { method, params, id } = req.body;

  switch (method) {
    case 'initialize':
      res.json({
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: 'netactor-toolbox',
            version: '1.0.0'
          }
        }
      });
      break;

    case 'tools/list':
      res.json({
        jsonrpc: '2.0',
        id,
        result: {
          tools: Object.values(TOOLS).map(tool => ({
            name: tool.name,
            description: tool.description,
            inputSchema: {
              type: 'object',
              properties: {
                target: { type: 'string', description: 'Target to scan (IP, CIDR, hostname)' },
                url: { type: 'string', description: 'Target URL' },
                domain: { type: 'string', description: 'Target domain' },
                protocol: { type: 'string', description: 'Protocol for nxc (smb, ldap, winrm, ssh, etc.)' },
                query: { type: 'string', description: 'Search query for searchsploit' },
                username: { type: 'string', description: 'Username for authenticated tools (adPEAS, nxc)' },
                password: { type: 'string', description: 'Password for authenticated tools (adPEAS, nxc)' },
                dc_ip: { type: 'string', description: 'Domain Controller IP for adPEAS' },
                flags: { type: 'string', description: 'Additional CLI flags' }
              }
            }
          }))
        }
      });
      break;

    case 'tools/call':
      const { name, arguments: args } = params;
      const tool = TOOLS[name];
      
      if (!tool) {
        res.json({
          jsonrpc: '2.0',
          id,
          error: { code: -32601, message: `Tool '${name}' not found` }
        });
        return;
      }

      try {
        const command = tool.command(args);
        const result = await executeCommand(command, args.timeout || 60000);
        
        res.json({
          jsonrpc: '2.0',
          id,
          result: {
            content: [{
              type: 'text',
              text: JSON.stringify(result, null, 2)
            }]
          }
        });
      } catch (error) {
        res.json({
          jsonrpc: '2.0',
          id,
          error: { code: -32000, message: error.message }
        });
      }
      break;

    default:
      res.json({
        jsonrpc: '2.0',
        id,
        error: { code: -32601, message: `Method '${method}' not supported` }
      });
  }
});

// Direct execution endpoint
app.post('/execute', async (req, res) => {
  const { command, timeout } = req.body;
  
  if (!command) {
    return res.status(400).json({ error: 'Command is required' });
  }

  const result = await executeCommand(command, timeout);
  res.json(result);
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', tools: Object.keys(TOOLS) });
});

// List available tools
app.get('/tools', (req, res) => {
  res.json(Object.keys(TOOLS));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`NetActor Toolbox MCP Server running on port ${PORT}`);
});
