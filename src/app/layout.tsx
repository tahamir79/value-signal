import type{Metadata}from"next";import"./globals.css";import{Shell}from"@/components/Shell";import{ConsoleProvider}from"@/components/ConsoleProvider";
export const metadata:Metadata={title:"ValueSignal Build Console",description:"A modular roadmap for building ValueSignal Lite."};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body><ConsoleProvider><Shell>{children}</Shell></ConsoleProvider></body></html>}
