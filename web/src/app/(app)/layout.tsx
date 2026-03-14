import { Sidebar } from "@/components/layout/Sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Sidebar />
      <main className="md:ml-64 min-h-screen px-4 pt-4 pb-24 md:p-8 md:pb-8">
        {children}
      </main>
    </>
  );
}
