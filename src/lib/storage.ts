import type { PhaseStatus } from "@/data/phases";
export type PhaseState={status:PhaseStatus;completed:string[]};
export type PhaseNote={currentIssue:string;solutionIdea:string;debugNotes:string;architectureDecision:string;resumeInsight:string;interviewStory:string;tags:string[];updatedAt:string};
export const emptyNote:PhaseNote={currentIssue:"",solutionIdea:"",debugNotes:"",architectureDecision:"",resumeInsight:"",interviewStory:"",tags:[],updatedAt:""};
export const keys={phase:(id:string)=>`vs:phase:${id}`,note:(id:string)=>`vs:note:${id}`};
export function read<T>(key:string,fallback:T):T { if(typeof window==="undefined")return fallback; try{return JSON.parse(localStorage.getItem(key)||"") as T}catch{return fallback} }
export function write<T>(key:string,value:T){localStorage.setItem(key,JSON.stringify(value));window.dispatchEvent(new Event("vs-storage"));}
