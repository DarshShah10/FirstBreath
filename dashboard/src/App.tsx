import { useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import Cursor from "@/components/system/Cursor";
import Preloader from "@/components/system/Preloader";
import PageTransition from "@/components/system/PageTransition";
import { SmoothScroll } from "@/lib/lenis";
import Home from "@/pages/Home";
import Declare from "@/pages/Declare";
import Run from "@/pages/Run";
import Debrief from "@/pages/Debrief";
import History from "@/pages/History";

function Shell() {
  const location = useLocation();

  useEffect(() => {
    document.body.classList.add("grain");
  }, []);

  return (
    <>
      <Preloader />
      <Cursor />
      <SmoothScroll>
        <PageTransition>
          <Routes location={location}>
            <Route path="/" element={<Home />} />
            <Route path="/new" element={<Declare />} />
            <Route path="/run/:simId" element={<Run />} />
            <Route path="/debrief/:simId" element={<Debrief />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </PageTransition>
      </SmoothScroll>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="grain min-h-screen bg-void text-bone">
        <Shell />
      </div>
    </BrowserRouter>
  );
}
