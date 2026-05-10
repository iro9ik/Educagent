import ClientApp from "@/components/ClientApp";

interface ChatPageProps {
  params: Promise<{ id: string }>;
}

export default async function ChatPage({ params }: ChatPageProps) {
  const { id } = await params;
  return <ClientApp initialChatId={id} />;
}
