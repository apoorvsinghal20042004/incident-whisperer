import { redirect } from "next/navigation";
// homepg redirects to /incidents
// incidents list is our real landing pg
export default function Home(){
  redirect("/incidents");
}