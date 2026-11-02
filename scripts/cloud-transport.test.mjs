import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sign,verify,safeFile} from './cloud-transport.mjs';
test('signature binds bytes, timestamp and purpose',()=>{
 const signature=sign('secret','request',100,'{}');
 assert.ok(verify('secret','request',100,'{}',signature,100));
 assert.ok(!verify('secret','response',100,'{}',signature,100));
 assert.ok(!verify('secret','request',100,'{"x":1}',signature,100));
 assert.ok(!verify('secret','request',100,'{}',signature,300101));
 assert.ok(!verify('secret','request',100,'{}','zz',100));
});
test('only ledger evidence is transferable, never credentials or traversal',()=>{
 for(const f of ['state.json','state-view.json','decisions/intent-15m-123.json','contexts/abc-def.json'])assert.ok(safeFile(f));
 for(const f of ['auth-token','worker.lock','../state.json','contexts/../../key','contexts/a/b.json','/state.json','contexts\\foo.json'])assert.ok(!safeFile(f));
});
