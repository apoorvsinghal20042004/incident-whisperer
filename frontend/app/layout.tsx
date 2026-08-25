// type — a TypeScript keyword meaning "I'm importing only the type definition, not actual code." 
// Metadata is a TypeScript type that defines the shape of our page metadata (title, description).
// uses this to catch mistakes — if you try to add a field that doesn't exist in Metadata, TypeScript errors immediately.
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// export means this is available to other files. metadata is a special Next.js export —
// when Next.js sees this in a layout or page file, it automatically puts the title and description in the HTML <head> tag.
// This is what shows in the browser tab and in Google search results.
export const metadata: Metadata = {
  title: "Incident Whisperer",
  description: "Autonomous oncall agent system: real time incident diagnosis",
};

// export default function — this is the main export of the file. 
// default means when someone imports this file without specifying a name, they get this function.
// { children } — this is the parameter. In React, children is a special prop that represents
// whatever is rendered inside this component. It is like a slot.
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={'${geistSans.variable} ${geistMono.variable}'}>
      <body className="min-h-screen bg-gray-950 text-gray-100 antialiased">
        {children}
      </body>
    </html>
  );
}