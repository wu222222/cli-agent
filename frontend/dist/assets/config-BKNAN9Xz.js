import{b as o}from"./agent-KvYckr-4.js";const n=async(e,s)=>(await o.post(`/command/${e}`,s?{command:s}:{})).data,r=async e=>(await o.post(`/composes/${e}/regenerate`)).data;export{n as e,r};
