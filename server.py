# ============================================================
# 1. IMPORTACIONES
# ============================================================

import warnings
import biosteam as bst

from biosteam.exceptions import CostWarning
from mcp.server.fastmcp import FastMCP

# ============================================================
# 2. CONFIGURACIÓN DEL SERVIDOR MCP
# ============================================================

# Inicializamos FastMCP con el nombre que Gemini reconocerá internamente.
mcp = FastMCP("BioSTEAM_Expert")

# ============================================================
# 3. CONFIGURACIÓN DE ADVERTENCIAS
# ============================================================

warnings.filterwarnings(
    "ignore",
    category=CostWarning
)

warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning
)

# ============================================================
# 4. CONFIGURACIÓN TERMODINÁMICA
# ============================================================

bst.main_flowsheet.clear()

bst.settings.set_thermo([
    "Water",
    "Hydrogen",
    "Oxygen",
    "CarbonDioxide",
    "Nitrogen",
    "Methanol"
])


# ============================================================
# 5. HERRAMIENTA MCP
# ============================================================

@mcp.tool()
def simular_produccion_metanol(flujo_agua: float) -> str:
    """
    Simula una planta de producción de metanol con recirculación.

    Parámetros
    ----------
    flujo_agua : float
        Flujo de alimentación de agua en kmol/hr.
        Como referencia, el modelo original recomienda
        aproximadamente 427 kmol/hr.

    Retorna
    -------
    str
        Resumen técnico de la simulación:
        - Flujo de producto
        - Pureza de metanol
        - Temperatura del producto
    """

    # ========================================================
    # VALIDACIÓN DE ENTRADA
    # ========================================================

    if flujo_agua <= 0:
        return (
            "❌ Error: el flujo de agua debe ser mayor que "
            "0 kmol/hr."
        )

    try:

        # ====================================================
        # 6. ALIMENTACIÓN DE AGUA
        # ====================================================

        feed_water = bst.Stream(
            "feed_water",
            Water=flujo_agua,
            units="kmol/hr"
        )


        # ====================================================
        # 7. BOMBA DE AGUA
        # ====================================================

        P1 = bst.Pump(
            "P1",
            ins=feed_water,
            outs="pressurized_water",
            P=80 * 101325
        )


        # ====================================================
        # 8. ENFRIADOR DE AGUA
        # ====================================================

        H1 = bst.HXutility(
            "H1",
            ins=P1 - 0,
            outs="cold_water",
            T=273.15 + 2.5
        )


        # ====================================================
        # 9. ELECTROLIZADOR
        # ====================================================

        class EnergyBasedElectrolyzer(bst.Unit):

            _N_ins = 1
            _N_outs = 2

            def __init__(
                self,
                ID="",
                ins=None,
                outs=(),
                thermo=None,
                kWh_per_kg_H2=50.0,
                conversion=0.85
            ):

                super().__init__(
                    ID,
                    ins,
                    outs,
                    thermo=thermo
                )

                self.kWh_per_kg_H2 = kWh_per_kg_H2
                self.conversion = conversion


            def _run(self):

                feed = self.ins[0]

                h2_stream = self.outs[0]
                o2_stream = self.outs[1]

                # --------------------------------------------
                # Agua de alimentación
                # --------------------------------------------

                water_in = feed.imol["Water"]

                # Conversión de agua
                water_reacted = (
                    water_in * self.conversion
                )

                water_left = (
                    water_in - water_reacted
                )


                # --------------------------------------------
                # Producción de H2 y O2
                # --------------------------------------------

                h2_mol_flow = water_reacted

                o2_mol_flow = (
                    water_reacted / 2.0
                )


                # --------------------------------------------
                # Corriente de H2
                # --------------------------------------------

                h2_stream.empty()

                h2_stream.phase = "g"

                h2_stream.imol["Hydrogen"] = (
                    h2_mol_flow
                )

                h2_stream.imol["Water"] = (
                    water_left * 0.01
                )

                h2_stream.T = (
                    88.8443 + 273.15
                )

                h2_stream.P = feed.P


                # --------------------------------------------
                # Corriente de O2
                # --------------------------------------------

                o2_stream.empty()

                o2_stream.phase = "g"

                o2_stream.imol["Oxygen"] = (
                    o2_mol_flow
                )

                o2_stream.imol["Water"] = (
                    water_left * 0.99
                )

                o2_stream.T = (
                    80.0 + 273.15
                )

                o2_stream.P = feed.P


            def _design(self):

                h2_mol_flow = (
                    self.outs[0].imol["Hydrogen"]
                )

                h2_mass_flow = (
                    h2_mol_flow * 2.016
                )

                power = (
                    h2_mass_flow *
                    self.kWh_per_kg_H2
                )

                self.add_power_utility(power)


        electrolyzer = EnergyBasedElectrolyzer(
            "E_lyzer",
            ins=H1 - 0,
            outs=("H2_raw", "O2_raw"),
            kWh_per_kg_H2=50.0,
            conversion=0.85
        )


        # ====================================================
        # 10. VÁLVULA DE HIDRÓGENO
        # ====================================================

        V1 = bst.units.IsenthalpicValve(
            "V1",
            ins=electrolyzer - 0,
            outs="H2_valved",
            P=60 * 101325,
            vle=True
        )


        # ====================================================
        # 11. ENFRIADOR DE HIDRÓGENO
        # ====================================================

        H2_cooler = bst.HXutility(
            "H2_cooler",
            ins=V1 - 0,
            outs="H2_cooled",
            T=40 + 273.15,
            dP=0.2 * 101325
        )


        # ====================================================
        # 12. ALIMENTACIÓN DE CO2
        # ====================================================

        feed_co2 = bst.Stream(
            "feed_co2",

            CarbonDioxide=(
                119.55 * 0.98
            ),

            Nitrogen=(
                119.55 * 0.02
            ),

            units="kmol/hr",

            phase="g",

            T=25 + 273.15,

            P=101325
        )


        # ====================================================
        # 13. COMPRESOR DE CO2
        # ====================================================

        K1 = bst.IsentropicCompressor(
            "K1",
            ins=feed_co2,
            outs="CO2_comp_out",
            P=60 * 101325,
            eta=0.80
        )


        # ====================================================
        # 14. ENFRIADOR DE CO2
        # ====================================================

        CO2_cooler = bst.HXutility(
            "CO2_cooler",
            ins=K1 - 0,
            outs="CO2_cooled",
            T=40 + 273.15,
            dP=0.2 * 101325
        )


        # ====================================================
        # 15. CORRIENTE DE RECIRCULACIÓN
        # ====================================================

        recirc_placeholder = bst.Stream(
            "Recirculacion_placeholder",
            phase="g"
        )


        # ====================================================
        # 16. MEZCLADOR PRINCIPAL
        # ====================================================

        M1 = bst.Mixer(
            "M1",

            ins=[
                H2_cooler - 0,
                CO2_cooler - 0,
                recirc_placeholder
            ],

            outs="mixed_high_pressure_stream"
        )


        # ====================================================
        # 17. PRECALENTAMIENTO
        # ====================================================

        E_300 = bst.HXutility(
            "E_300",
            ins=M1 - 0,
            outs="S-301",
            T=220 + 273.15,
            dP=0.2 * 101325
        )


        # ====================================================
        # 18. DIVISOR DE FLUJO
        # ====================================================

        RNX_0 = bst.Stream("RNX_0")

        RNX_1 = bst.Stream("RNX_1")


        Splitter_1 = bst.Splitter(
            "Splitter_1",

            ins=E_300 - 0,

            outs=[
                RNX_0,
                RNX_1
            ],

            split=0.5
        )


        # ====================================================
        # 19. REACCIONES QUÍMICAS
        # ====================================================

        reaction_R1 = bst.Reaction(
            "CarbonDioxide + 3Hydrogen -> Methanol + Water",

            reactant="CarbonDioxide",

            X=0.99,

            correct_atomic_balance=True
        )


        reaction_R2 = bst.Reaction(
            "CarbonDioxide + 3Hydrogen -> Methanol + Water",

            reactant="CarbonDioxide",

            X=0.99,

            correct_atomic_balance=True
        )


        # ====================================================
        # 20. REACTOR DE CONVERSIÓN DE METANOL
        # ====================================================

        class MethanolConversionReactor(bst.Unit):

            _N_ins = 1
            _N_outs = 1

            def __init__(
                self,
                ID="",
                ins=None,
                outs=None,
                reaction=None,
                T=523.15,
                P=60e5,
                thermo=None
            ):

                super().__init__(
                    ID,
                    ins=ins,
                    outs=outs,
                    thermo=thermo
                )

                self.reaction = reaction
                self.T = T
                self.P = P


            def _run(self):

                feed = self.ins[0]

                product = self.outs[0]

                # Copiar composición
                product.copy_like(feed)

                # Condiciones del reactor
                product.T = self.T
                product.P = self.P
                product.phase = "g"

                # Aplicar reacción
                self.reaction(product)


            def _design(self):
                pass


        # ====================================================
        # 21. REACTORES R1 Y R2
        # ====================================================

        R1 = MethanolConversionReactor(
            "R1",

            ins=RNX_0,

            outs="r1_out",

            reaction=reaction_R1,

            T=250 + 273.15,

            P=60e5
        )


        R2 = MethanolConversionReactor(
            "R2",

            ins=RNX_1,

            outs="r2_out",

            reaction=reaction_R2,

            T=250 + 273.15,

            P=60e5
        )


        # ====================================================
        # 22. ENFRIAMIENTO POST-REACCIÓN
        # ====================================================

        E_400 = bst.HXutility(
            "E_400",
            ins=R1 - 0,
            outs="S-401",
            T=10 + 273.15,
            dP=0.2 * 101325
        )


        E_500 = bst.HXutility(
            "E_500",
            ins=R2 - 0,
            outs="S-501",
            T=10 + 273.15,
            dP=0.2 * 101325
        )


        # ====================================================
        # 23. VÁLVULAS DE EXPANSIÓN
        # ====================================================

        V_flash_1 = bst.units.IsenthalpicValve(
            "V_flash_1",
            ins=E_400 - 0,
            outs="S_valved_1",
            P=25 * 101325,
            vle=True
        )


        V_flash_2 = bst.units.IsenthalpicValve(
            "V_flash_2",
            ins=E_500 - 0,
            outs="S_valved_2",
            P=25 * 101325,
            vle=True
        )


        # ====================================================
        # 24. TANQUES FLASH
        # ====================================================

        V_pobre_1 = bst.Stream(
            "V_pobre_1"
        )

        L_rico_1 = bst.Stream(
            "L_rico_1"
        )

        V_pobre_2 = bst.Stream(
            "V_pobre_2"
        )

        L_rico_2 = bst.Stream(
            "L_rico_2"
        )


        flash_1 = bst.Flash(
            "flash_1",

            ins=V_flash_1 - 0,

            outs=[
                V_pobre_1,
                L_rico_1
            ],

            T=5 + 273.15,

            P=20 * 101325
        )


        flash_2 = bst.Flash(
            "flash_2",

            ins=V_flash_2 - 0,

            outs=[
                V_pobre_2,
                L_rico_2
            ],

            T=5 + 273.15,

            P=20 * 101325
        )


        # ====================================================
        # 25. MEZCLADORES DE VAPOR Y LÍQUIDO
        # ====================================================

        M2 = bst.Mixer(
            "M2",

            ins=[
                V_pobre_1,
                V_pobre_2
            ],

            outs="mixed_vapor_out"
        )


        M3 = bst.Mixer(
            "M3",

            ins=[
                L_rico_1,
                L_rico_2
            ],

            outs="mixed_liquid_product"
        )


        # ====================================================
        # 26. VÁLVULA PREVIA A DESTILACIÓN
        # ====================================================

        V_preC = bst.units.IsenthalpicValve(
            "V_preC",

            ins=M3 - 0,

            outs="Me_PreC",

            P=1 * 101325,

            vle=True
        )


        # ====================================================
        # 27. COLUMNA DE DESTILACIÓN
        # ====================================================

        D1 = bst.BinaryDistillation(
            "D1",

            ins=V_preC.outs[0],

            outs=(
                "distillate_methanol",
                "bottoms_wastewater"
            ),

            LHK=(
                "Methanol",
                "Water"
            ),

            y_top=0.9988,

            x_bot=0.00001,

            k=1.25
        )


        # ====================================================
        # 28. RECIRCULACIÓN
        # ====================================================

        K2 = bst.IsentropicCompressor(
            "K2",

            ins=M2 - 0,

            outs="C_pobre",

            P=60 * 101325,

            eta=0.80
        )


        # ====================================================
        # 29. ENFRIADOR DE RECIRCULACIÓN
        # ====================================================

        E_600 = bst.HXutility(
            "E_600",

            ins=K2 - 0,

            outs="S-601",

            T=2.5 + 273.15,

            dP=0.2 * 101325
        )


        # ====================================================
        # 30. VÁLVULA DEL FLASH 3
        # ====================================================

        V_flash_3 = bst.units.IsenthalpicValve(
            "V_flash_3",

            ins=E_600 - 0,

            outs="S_valved_3",

            P=25 * 101325,

            vle=True
        )


        # ====================================================
        # 31. FLASH 3
        # ====================================================

        Pre_Purga = bst.Stream(
            "Pre_Purga"
        )

        Posible_Drenaje = bst.Stream(
            "Posible_Drenaje"
        )


        flash_3 = bst.Flash(
            "flash_3",

            ins=V_flash_3 - 0,

            outs=[
                Pre_Purga,
                Posible_Drenaje
            ],

            T=5 + 273.15,

            P=1.5 * 101325
        )


        # ====================================================
        # 32. PURGA
        # ====================================================

        Pre_Recir = bst.Stream(
            "Pre_Recir"
        )

        Purga = bst.Stream(
            "Purga"
        )


        Splitter_2 = bst.Splitter(
            "Splitter_2",

            ins=flash_3 - 0,

            outs=[
                Pre_Recir,
                Purga
            ],

            split=0.985
        )


        # ====================================================
        # 33. COMPRESOR DE RECIRCULACIÓN
        # ====================================================

        K3 = bst.IsentropicCompressor(
            "K3",

            ins=Splitter_2 - 0,

            outs="Pre_Cool",

            P=60 * 101325,

            eta=0.80
        )


        K3.outs[0].phase = "g"


        # ====================================================
        # 34. ENFRIADOR FINAL DE RECIRCULACIÓN
        # ====================================================

        E_700 = bst.HXutility(
            "E_700",

            ins=K3 - 0,

            outs="Recirculacion",

            T=40 + 273.15,

            dP=0.2 * 101325
        )


        # ====================================================
        # 35. CERRAR EL LAZO DE RECIRCULACIÓN
        # ====================================================

        M1.ins[2] = E_700 - 0


        # ====================================================
        # 36. CREAR SISTEMA DE BIOSTEAM
        # ====================================================

        sys = bst.main_flowsheet.create_system()


        # ====================================================
        # 37. TOLERANCIAS
        # ====================================================

        sys.set_tolerance(
            mol=1e-4,
            T=1e-3
        )


        # ====================================================
        # 38. EJECUTAR SIMULACIÓN
        # ====================================================

        sys.simulate()


        # ====================================================
        # 39. OBTENER PRODUCTO
        # ====================================================

        prod = D1.outs[0]


        # ====================================================
        # 40. CALCULAR PUREZA
        # ====================================================

        if prod.F_mass > 0:

            pureza_masa = (
                prod.imass["Methanol"]
                / prod.F_mass
            ) * 100

        else:

            pureza_masa = 0.0


        # ====================================================
        # 41. RESULTADOS
        # ====================================================

        flujo_producto = prod.F_mass

        temperatura_producto = (
            prod.T - 273.15
        )


        # ====================================================
        # 42. RESUMEN
        # ====================================================

        resumen = (

            "========================================\n"
            " SIMULACIÓN DE PRODUCCIÓN DE METANOL\n"
            "========================================\n\n"

            "RESULTADO: SIMULACIÓN COMPLETADA\n\n"

            f"Flujo de agua de alimentación: "
            f"{flujo_agua:,.2f} kmol/hr\n\n"

            "PRODUCTO DE METANOL\n"
            "----------------------------------------\n"

            f"Flujo de producto: "
            f"{flujo_producto:,.2f} kg/hr\n"

            f"Pureza de metanol: "
            f"{pureza_masa:.2f} % p/p\n"

            f"Temperatura del producto: "
            f"{temperatura_producto:.2f} °C\n"

        )


        return resumen


    # ========================================================
    # 43. MANEJO DE ERRORES
    # ========================================================

    except Exception as e:

        return (
            "========================================\n"
            " ERROR EN LA SIMULACIÓN\n"
            "========================================\n\n"
            f"{type(e).__name__}: {str(e)}"
        )


# ============================================================
# 4. PUNTO DE ENTRADA
if __name__ == "__main__":
    mcp.run()
