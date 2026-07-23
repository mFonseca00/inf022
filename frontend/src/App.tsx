import { BrowserRouter, Routes, Route } from "react-router-dom";
import ProcessosList from "./pages/ProcessosList";
import NovoProcesso from "./pages/NovoProcesso";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProcessosList />} />
        <Route path="/novo" element={<NovoProcesso />} />
        <Route path="/processo/:processoId" element={<NovoProcesso />} />
      </Routes>
    </BrowserRouter>
  );
}
