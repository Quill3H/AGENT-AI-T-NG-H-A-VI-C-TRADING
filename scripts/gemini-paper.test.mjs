import {test} from 'node:test';
import assert from 'node:assert/strict';
import {geminiJson,requireState,validateManagement} from './gemini-paper.mjs';
test('malformed management rationale cannot be decorated into a valid reason',()=>{
 assert.throws(()=>validateManagement({management:[{tradeId:'a',action:'CLOSE'}]},[{id:'a',status:'OPEN'}]),/reason/);
 assert.throws(()=>validateManagement({management:[{tradeId:'a',action:'UPDATE_LEVELS',reason:'test',sl:'12'}]},[{id:'a',status:'OPEN'}]),/levels/);
});
test('missing state cannot create fresh wallets',async()=>{
 await assert.rejects(requireState('/a/nonexistent/paper-state.json'),/migrated state/);
});
test('missing key makes no API call',async()=>{
 await assert.rejects(geminiJson({}, {key:'',model:'test',fetcher:()=>assert.fail('network')}),/GEMINI_API_KEY/);
});
test('provider errors do not become HOLD or successful decisions',async()=>{
 await assert.rejects(geminiJson({}, {key:'secret',model:'test',fetcher:async()=>({ok:false,status:429})}),/429/);
});
test('parse only completed JSON and never return API key',async()=>{
 const response=await geminiJson({x:1},{key:'secret',model:'test',fetcher:async(url,options)=>{
  assert.equal(options.headers['x-goog-api-key'],'secret');assert.ok(!url.includes('secret'));
  return {ok:true,json:async()=>({modelVersion:'test-v1',candidates:[{finishReason:'STOP',content:{parts:[{text:'{"entry":null}'}]}}]})};
 }});assert.deepEqual(response,{value:{entry:null},modelVersion:'test-v1'});
});
