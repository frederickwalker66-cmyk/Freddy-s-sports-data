import {test} from "node:test";
import assert from "node:assert/strict";
import {EMPLOYEES, readiness, validateZoomMeetingUrl, SixAgentZoomCoordinator} from "../src/zoom.mjs";

test("only valid Zoom invite URLs are accepted",()=>{
  assert.equal(validateZoomMeetingUrl("https://us02web.zoom.us/j/12345678901?pwd=one"),true);
  for(const url of ["https://zoom.us.evil.org/j/12345678901","http://zoom.us/j/12345678901",
    "https://zoom.us@evil.org/j/12345678901","https://zoom.us/j/1",
    "https://zoom.us/j/12345678901#token","https://zoom.us/j/12345678901?redirect=evil"]){
    assert.equal(validateZoomMeetingUrl(url),false,url);
  }
});

test("readiness is conservative and does not contact a provider",()=>{
  const report=readiness({});
  assert.equal(report.status,"NOT_READY");
  assert.equal(report.required_participants,6);
  assert.equal(report.connected_participants,0);
  assert.equal(report.zoom_meeting_created,false);
  assert.equal(report.paid_call_started,false);
  assert.equal(report.whatsapp_native_video_supported,false);
  assert.equal(EMPLOYEES.length,6);
  assert.equal(new Set(EMPLOYEES.map(p=>p.role)).size,6);
});

test("cannot join meeting without CEO authorization, explicit start, and cost consent",async()=>{
  let joins=0;
  const coordinator=new SixAgentZoomCoordinator({
    async joinParticipant(){joins++;return{joined:true,participantId:joins}},
    async leaveParticipant(){},
  });
  const valid="https://zoom.us/j/12345678901";
  for(const opts of [
    {authorizedCEO:false,explicitStart:true,costsApproved:true},
    {authorizedCEO:true,explicitStart:false,costsApproved:true},
    {authorizedCEO:true,explicitStart:true,costsApproved:false},
  ]){
    await assert.rejects(coordinator.joinAll({...opts,meetingUrl:valid}));
  }
  assert.equal(joins,0);
  assert.equal(coordinator.status.count,0);
});

test("mock six bot joins and teardown require unique Zoom participant receipts",async()=>{
  const joined=[],left=[];
  const coordinator=new SixAgentZoomCoordinator({
    async joinParticipant(p){joined.push(p.role);return {joined:true,participantId:"zoom-"+p.role}},
    async leaveParticipant(p){left.push(p.role)},
  });
  const result=await coordinator.joinAll({authorizedCEO:true,explicitStart:true,costsApproved:true,
    meetingUrl:"https://zoom.us/j/12345678901"});
  assert.equal(result.count,6);
  assert.deepEqual(joined,EMPLOYEES.map(x=>x.role));
  assert.equal((await coordinator.leaveAll()).count,0);
  assert.equal(left.length,6);
});

test("mock partial join failure rolls back previous participants",async()=>{
  const left=[];
  const coordinator=new SixAgentZoomCoordinator({
    async joinParticipant(p){
      if(p.role==="cassidy")return {joined:false};
      return {joined:true,participantId:p.role};
    },
    async leaveParticipant(p){left.push(p.role)},
  });
  await assert.rejects(coordinator.joinAll({
    authorizedCEO:true,explicitStart:true,costsApproved:true,
    meetingUrl:"https://zoom.us/j/12345678901"
  }));
  assert.deepEqual(left,["david","bella"]);
  assert.equal(coordinator.status.count,0);
});
